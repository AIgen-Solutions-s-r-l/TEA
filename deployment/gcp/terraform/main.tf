# Terraform configuration for GCP Weather Platform deployment

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west1"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])
  
  service = each.value
}

# Create service account
resource "google_service_account" "weather_platform" {
  account_id   = "weather-platform-sa"
  display_name = "Weather Platform Service Account"
}

# Grant necessary roles
resource "google_project_iam_member" "roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor",
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.weather_platform.email}"
}

# Create Artifact Registry repository
resource "google_artifact_registry_repository" "weather_platform" {
  location      = var.region
  repository_id = "weather-platform"
  format        = "DOCKER"
  
  depends_on = [google_project_service.apis]
}

# Create Cloud SQL instance
resource "google_sql_database_instance" "weather_db" {
  name             = "weather-db"
  database_version = "POSTGRES_16"
  region           = var.region
  
  settings {
    tier = "db-g1-small"
    
    database_flags {
      name  = "max_connections"
      value = "100"
    }
    
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }
    
    maintenance_window {
      day          = 7  # Sunday
      hour         = 3
      update_track = "stable"
    }
  }
  
  deletion_protection = true
  depends_on          = [google_project_service.apis]
}

# Create database
resource "google_sql_database" "weather_db" {
  name     = "weather_db"
  instance = google_sql_database_instance.weather_db.name
}

# Create database user
resource "google_sql_user" "weather_user" {
  name     = "weather_user"
  instance = google_sql_database_instance.weather_db.name
  password = var.db_password
}

# Store database password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "weather-db-password"
  
  replication {
    auto {}
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

# Grant secret access to service account
resource "google_secret_manager_secret_iam_member" "db_password_access" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.weather_platform.email}"
}

# Create Cloud Storage bucket
resource "google_storage_bucket" "weather_data" {
  name          = "${var.project_id}-weather-data"
  location      = var.region
  force_destroy = false
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 30
      matches_prefix = ["processed/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  
  lifecycle_rule {
    condition {
      age = 365
      matches_prefix = ["processed/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }
}

# Cloud Run service
resource "google_cloud_run_v2_service" "weather_dashboard" {
  name     = "weather-dashboard"
  location = var.region
  
  template {
    service_account = google_service_account.weather_platform.email
    
    scaling {
      min_instance_count = 1
      max_instance_count = 100
    }
    
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/weather-platform/dashboard:latest"
      
      ports {
        container_port = 8080
      }
      
      env {
        name  = "DB_HOST"
        value = "/cloudsql/${google_sql_database_instance.weather_db.connection_name}"
      }
      
      env {
        name  = "DB_PORT"
        value = "5432"
      }
      
      env {
        name  = "DB_NAME"
        value = "weather_db"
      }
      
      env {
        name  = "DB_USER"
        value = "weather_user"
      }
      
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }
    
    vpc_access {
      network_interfaces {
        network = "default"
      }
    }
    
    annotations = {
      "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.weather_db.connection_name
    }
  }
  
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  
  depends_on = [
    google_sql_database.weather_db,
    google_sql_user.weather_user,
    google_secret_manager_secret_version.db_password,
  ]
}

# Allow public access
resource "google_cloud_run_service_iam_member" "public" {
  service  = google_cloud_run_v2_service.weather_dashboard.name
  location = google_cloud_run_v2_service.weather_dashboard.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "service_url" {
  value = google_cloud_run_v2_service.weather_dashboard.uri
}

output "bucket_name" {
  value = google_storage_bucket.weather_data.name
}

output "sql_connection_name" {
  value = google_sql_database_instance.weather_db.connection_name
}