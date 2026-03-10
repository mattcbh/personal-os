output "triage_api_url" {
  value = google_cloud_run_v2_service.triage_api.uri
}

output "triage_worker_url" {
  value = google_cloud_run_v2_service.triage_worker.uri
}

output "artifact_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "run_queue" {
  value = google_cloud_tasks_queue.triage_run.name
}

output "db_instance_connection_name" {
  value = google_sql_database_instance.triage.connection_name
}
