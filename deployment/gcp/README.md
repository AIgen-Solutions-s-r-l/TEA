# Deploying Weather Data Platform to Google Cloud Platform

This guide covers multiple deployment options for the Weather Data Platform on GCP.

## Prerequisites

1. GCP Account with billing enabled
2. Google Cloud SDK (`gcloud`) installed locally
3. Docker installed locally
4. Project ID created in GCP Console

## Deployment Options

### Option 1: Google Cloud Run (Recommended for Simplicity)

Best for: Quick deployment, automatic scaling, serverless approach

**Pros:**
- Fully managed
- Automatic HTTPS
- Pay per use
- Auto-scaling

**Cons:**
- Cold starts possible
- Stateless (need external database)

### Option 2: Google Kubernetes Engine (GKE)

Best for: Production workloads, full control, complex deployments

**Pros:**
- Full Kubernetes features
- Better for stateful applications
- More control over resources

**Cons:**
- More complex setup
- Higher base cost

### Option 3: Compute Engine with Docker

Best for: Simple VM deployment, full control, persistent storage

**Pros:**
- Simple migration from local Docker
- Persistent local storage
- Full VM control

**Cons:**
- Manual scaling
- Need to manage VM updates

## Quick Start: Cloud Run Deployment

```bash
# Set up environment
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1

# Authenticate
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create weather-platform \
    --repository-format=docker \
    --location=$REGION

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push images
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest -f app/Dockerfile ./app
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest

# Deploy to Cloud Run
gcloud run deploy weather-dashboard \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "DB_HOST=your-cloud-sql-ip,DB_PORT=5432,DB_NAME=weather_db,DB_USER=weather_user" \
    --set-secrets "DB_PASSWORD=weather-db-password:latest"
```

## Detailed Deployment Guides

- [Cloud Run Deployment](./cloud-run-deployment.md)
- [GKE Deployment](./gke-deployment.md)
- [Compute Engine Deployment](./compute-engine-deployment.md)