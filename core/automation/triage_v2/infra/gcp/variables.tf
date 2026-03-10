variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-east1"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL machine tier"
  default     = "db-custom-1-3840"
}

variable "db_user" {
  type        = string
  description = "Cloud SQL app username"
  default     = "triage_app"
}

variable "db_password" {
  type        = string
  description = "Cloud SQL app password"
  sensitive   = true
}

variable "container_image" {
  type        = string
  description = "Container image for triage API/worker"
}

variable "timezone" {
  type        = string
  description = "Scheduler timezone"
  default     = "America/New_York"
}
