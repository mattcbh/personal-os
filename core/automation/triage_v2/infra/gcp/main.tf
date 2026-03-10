provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  service_name_prefix = "email-triage-v2"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudtasks.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "triage_sa" {
  account_id   = "email-triage-v2-sa"
  display_name = "Email Triage v2 runtime service account"
}

resource "google_storage_bucket" "artifacts" {
  name          = "${var.project_id}-email-triage-v2-artifacts"
  location      = var.region
  force_destroy = false
  uniform_bucket_level_access = true
}

resource "google_sql_database_instance" "triage" {
  name             = "email-triage-v2-db"
  region           = var.region
  database_version = "POSTGRES_16"
  deletion_protection = true

  settings {
    tier = var.db_tier
    backup_configuration {
      enabled = true
    }
    ip_configuration {
      ipv4_enabled = false
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "triage" {
  name     = "triage"
  instance = google_sql_database_instance.triage.name
}

resource "google_sql_user" "triage" {
  instance = google_sql_database_instance.triage.name
  name     = var.db_user
  password = var.db_password
}

resource "google_secret_manager_secret" "gmail_work_oauth" {
  secret_id = "gmail-work-oauth-json"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "gmail_personal_oauth" {
  secret_id = "gmail-personal-oauth-json"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "llm_api_key" {
  secret_id = "triage-llm-api-key"
  replication {
    auto {}
  }
}

resource "google_cloud_tasks_queue" "triage_run" {
  name     = "triage-run-queue"
  location = var.region

  retry_config {
    max_attempts = 10
  }
}

resource "google_cloud_tasks_queue" "draft" {
  name     = "triage-draft-queue"
  location = var.region

  retry_config {
    max_attempts = 12
  }
}

resource "google_cloud_tasks_queue" "send" {
  name     = "triage-send-queue"
  location = var.region

  retry_config {
    max_attempts = 8
  }
}

resource "google_cloud_tasks_queue" "reconcile" {
  name     = "triage-reconcile-queue"
  location = var.region

  retry_config {
    max_attempts = 6
  }
}

resource "google_cloud_run_v2_service" "triage_api" {
  name     = "triage-api"
  location = var.region

  template {
    service_account = google_service_account.triage_sa.email

    containers {
      image = var.container_image
      args  = ["python3", "-m", "triage_v2", "serve-api", "--host", "0.0.0.0", "--port", "8080"]

      env {
        name  = "TRIAGE_V2_PROVIDER_MODE"
        value = "gmail"
      }
      env {
        name  = "TRIAGE_V2_SENDER_MODE"
        value = "gmail"
      }
      env {
        name  = "TRIAGE_V2_DRAFT_MODE"
        value = "superhuman_preferred"
      }
      env {
        name  = "TRIAGE_V2_ARTIFACT_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "triage_worker" {
  name     = "triage-worker"
  location = var.region

  template {
    service_account = google_service_account.triage_sa.email

    containers {
      image = var.container_image
      args  = ["python3", "-m", "triage_v2", "worker-loop", "--sleep-seconds", "2"]

      env {
        name  = "TRIAGE_V2_PROVIDER_MODE"
        value = "gmail"
      }
      env {
        name  = "TRIAGE_V2_SENDER_MODE"
        value = "gmail"
      }
      env {
        name  = "TRIAGE_V2_DRAFT_MODE"
        value = "superhuman_preferred"
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "triage_am" {
  name      = "triage-v2-am"
  schedule  = "0 6 * * *"
  time_zone = var.timezone

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.triage_api.uri}/triage/runs"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({
      run_type        = "am",
      force_reconcile = true,
    }))
  }
}

resource "google_cloud_scheduler_job" "triage_pm" {
  name      = "triage-v2-pm"
  schedule  = "0 15 * * *"
  time_zone = var.timezone

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.triage_api.uri}/triage/runs"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({
      run_type        = "pm",
      force_reconcile = false,
    }))
  }
}
