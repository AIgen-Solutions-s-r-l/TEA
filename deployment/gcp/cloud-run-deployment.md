# Cloud Run Deployment Guide

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Cloud CDN     │────▶│   Cloud Run      │────▶│  Cloud SQL      │
│  (Optional)     │     │  (Dashboard)     │     │  (PostgreSQL)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ Cloud Storage    │     │ Cloud SQL Proxy │
                        │ (CSV Files)      │     │                 │
                        └──────────────────┘     └─────────────────┘
```

## Step 1: Set Up Cloud SQL

```bash
# Create Cloud SQL instance
gcloud sql instances create weather-db \
    --database-version=POSTGRES_16 \
    --tier=db-g1-small \
    --region=$REGION \
    --network=default \
    --database-flags=max_connections=100

# Create database and user
gcloud sql databases create weather_db --instance=weather-db
gcloud sql users create weather_user --instance=weather-db --password=<secure-password>

# Get connection name for later use
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe weather-db --format="value(connectionName)")
```

## Step 2: Prepare Application for Cloud Run

Create a new Dockerfile optimized for Cloud Run:

```dockerfile
# deployment/gcp/Dockerfile.cloudrun
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run uses PORT environment variable
ENV PORT=8080
EXPOSE 8080

# Run with Cloud SQL Proxy support
CMD streamlit run streamlit_app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.serverAddress=0.0.0.0 \
    --browser.gatherUsageStats=false
```

## Step 3: Create Cloud Run Service Configuration

```yaml
# deployment/gcp/service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: weather-dashboard
  annotations:
    run.googleapis.com/launch-stage: GA
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cloudsql-instances: PROJECT_ID:REGION:weather-db
        run.googleapis.com/execution-environment: gen2
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "100"
    spec:
      serviceAccountName: weather-platform-sa
      containerConcurrency: 100
      timeoutSeconds: 300
      containers:
      - image: REGION-docker.pkg.dev/PROJECT_ID/weather-platform/dashboard:latest
        ports:
        - name: http1
          containerPort: 8080
        env:
        - name: DB_HOST
          value: "/cloudsql/PROJECT_ID:REGION:weather-db"
        - name: DB_PORT
          value: "5432"
        - name: DB_NAME
          value: "weather_db"
        - name: DB_USER
          value: "weather_user"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: weather-db-password
              key: latest
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
          requests:
            cpu: "1"
            memory: "1Gi"
```

## Step 4: Set Up Cloud Storage for CSV Files

```bash
# Create bucket for CSV files
gsutil mb -l $REGION gs://${PROJECT_ID}-weather-data

# Upload CSV files
gsutil -m cp RAW_DATA/*.csv gs://${PROJECT_ID}-weather-data/raw/

# Set up lifecycle rule to move processed files
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {
          "age": 30,
          "matchesPrefix": ["processed/"]
        }
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://${PROJECT_ID}-weather-data
```

## Step 5: Create ETL Cloud Function

```python
# deployment/gcp/etl_function/main.py
import os
import pandas as pd
import psycopg2
from google.cloud import storage
import functions_framework

@functions_framework.cloud_event
def process_weather_csv(cloud_event):
    """Triggered by CSV upload to Cloud Storage"""
    data = cloud_event.data
    
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    # Skip if not a CSV or already processed
    if not file_name.endswith('.csv') or file_name.startswith('processed/'):
        return
    
    # Download file
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    local_file = f"/tmp/{os.path.basename(file_name)}"
    blob.download_to_filename(local_file)
    
    # Process with existing ETL logic
    # ... (import your ETL code here)
    
    # Move to processed
    new_blob = bucket.blob(f"processed/{os.path.basename(file_name)}")
    bucket.copy_blob(blob, bucket, new_blob.name)
    blob.delete()
    
    return {"status": "success", "file": file_name}
```

## Step 6: Deploy Everything

```bash
# Create service account
gcloud iam service-accounts create weather-platform-sa \
    --display-name="Weather Platform Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Create secret for database password
echo -n "your-secure-password" | gcloud secrets create weather-db-password --data-file=-

# Grant secret access
gcloud secrets add-iam-policy-binding weather-db-password \
    --member="serviceAccount:weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Build and deploy
gcloud builds submit --config=deployment/gcp/cloudbuild.yaml
gcloud run services replace deployment/gcp/service.yaml --region=$REGION

# Deploy ETL Cloud Function
gcloud functions deploy process-weather-csv \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=deployment/gcp/etl_function \
    --entry-point=process_weather_csv \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=${PROJECT_ID}-weather-data" \
    --trigger-location=$REGION \
    --service-account=weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com
```

## Step 7: Configure Custom Domain (Optional)

```bash
# Map custom domain
gcloud run domain-mappings create \
    --service=weather-dashboard \
    --domain=weather.yourdomain.com \
    --region=$REGION

# The command will output DNS records to configure
```

## Monitoring and Logging

```bash
# View logs
gcloud run services logs read weather-dashboard --region=$REGION

# Set up monitoring alert
gcloud alpha monitoring policies create \
    --notification-channels=YOUR_CHANNEL_ID \
    --display-name="Weather Dashboard High Error Rate" \
    --condition-display-name="Error rate above 5%" \
    --condition-threshold-value=0.05 \
    --condition-threshold-duration=60s
```

## Cost Optimization

1. **Use Cloud Run minimum instances = 0** for development
2. **Set maximum instances** to prevent bill shock
3. **Use Cloud SQL shared tier** for development
4. **Enable Cloud CDN** for static assets
5. **Set up budget alerts**

```bash
# Create budget alert
gcloud billing budgets create \
    --billing-account=YOUR_BILLING_ACCOUNT \
    --display-name="Weather Platform Budget" \
    --budget-amount=100 \
    --threshold-rule=percent=0.5,basis=current-spend \
    --threshold-rule=percent=0.9,basis=current-spend \
    --threshold-rule=percent=1.0,basis=current-spend
```

## Security Best Practices

1. **Enable Cloud Armor** for DDoS protection
2. **Use Secret Manager** for all sensitive data
3. **Enable VPC Service Controls**
4. **Set up Cloud IAP** for authentication
5. **Regular security scanning**

```bash
# Enable Cloud IAP
gcloud run services add-iam-policy-binding weather-dashboard \
    --region=$REGION \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --condition=None

# Configure IAP
gcloud iap web enable \
    --resource-type=backend-services \
    --service=weather-dashboard
```