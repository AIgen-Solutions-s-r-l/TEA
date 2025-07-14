#!/bin/bash

# Weather Platform Quick Deploy Script for GCP
# This script deploys the Weather Platform to Google Cloud Run with Cloud SQL

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install Google Cloud SDK."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
}

# Get project configuration
get_config() {
    print_status "Getting configuration..."
    
    # Get current project ID
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    
    read -p "Enter GCP Project ID [$CURRENT_PROJECT]: " PROJECT_ID
    PROJECT_ID=${PROJECT_ID:-$CURRENT_PROJECT}
    
    read -p "Enter GCP Region [europe-west1]: " REGION
    REGION=${REGION:-europe-west1}
    
    read -p "Enter database password (min 8 chars): " -s DB_PASSWORD
    echo
    
    if [ ${#DB_PASSWORD} -lt 8 ]; then
        print_error "Database password must be at least 8 characters"
        exit 1
    fi
    
    export PROJECT_ID REGION DB_PASSWORD
}

# Enable required APIs
enable_apis() {
    print_status "Enabling required GCP APIs..."
    
    gcloud services enable \
        run.googleapis.com \
        sqladmin.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        --project=$PROJECT_ID
}

# Create Artifact Registry repository
create_artifact_registry() {
    print_status "Creating Artifact Registry repository..."
    
    if ! gcloud artifacts repositories describe weather-platform \
        --location=$REGION --project=$PROJECT_ID &> /dev/null; then
        gcloud artifacts repositories create weather-platform \
            --repository-format=docker \
            --location=$REGION \
            --project=$PROJECT_ID
    else
        print_warning "Artifact Registry repository already exists"
    fi
    
    # Configure Docker authentication
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
}

# Create Cloud SQL instance
create_cloud_sql() {
    print_status "Creating Cloud SQL instance..."
    
    if ! gcloud sql instances describe weather-db \
        --project=$PROJECT_ID &> /dev/null; then
        gcloud sql instances create weather-db \
            --database-version=POSTGRES_16 \
            --tier=db-g1-small \
            --region=$REGION \
            --project=$PROJECT_ID
        
        # Wait for instance to be ready
        print_status "Waiting for Cloud SQL instance to be ready..."
        gcloud sql operations wait --project=$PROJECT_ID \
            $(gcloud sql operations list --instance=weather-db \
                --project=$PROJECT_ID --format="value(name)" --limit=1)
        
        # Create database
        gcloud sql databases create weather_db \
            --instance=weather-db \
            --project=$PROJECT_ID
        
        # Create user
        gcloud sql users create weather_user \
            --instance=weather-db \
            --password=$DB_PASSWORD \
            --project=$PROJECT_ID
    else
        print_warning "Cloud SQL instance already exists"
    fi
    
    # Get instance connection name
    export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe weather-db \
        --project=$PROJECT_ID --format="value(connectionName)")
}

# Create service account
create_service_account() {
    print_status "Creating service account..."
    
    if ! gcloud iam service-accounts describe \
        weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com \
        --project=$PROJECT_ID &> /dev/null; then
        gcloud iam service-accounts create weather-platform-sa \
            --display-name="Weather Platform Service Account" \
            --project=$PROJECT_ID
    fi
    
    # Grant necessary roles
    for role in cloudsql.client storage.objectViewer secretmanager.secretAccessor; do
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com" \
            --role="roles/$role" \
            --condition=None
    done
}

# Create secrets
create_secrets() {
    print_status "Creating secrets..."
    
    # Create or update database password secret
    if ! gcloud secrets describe weather-db-password \
        --project=$PROJECT_ID &> /dev/null; then
        echo -n "$DB_PASSWORD" | gcloud secrets create weather-db-password \
            --data-file=- \
            --project=$PROJECT_ID
    else
        echo -n "$DB_PASSWORD" | gcloud secrets versions add weather-db-password \
            --data-file=- \
            --project=$PROJECT_ID
    fi
    
    # Grant access to service account
    gcloud secrets add-iam-policy-binding weather-db-password \
        --member="serviceAccount:weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --project=$PROJECT_ID
}

# Build and push Docker image
build_and_push_image() {
    print_status "Building and pushing Docker image..."
    
    IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest"
    
    # Build image
    docker build -t $IMAGE_URL -f app/Dockerfile ./app
    
    # Push image
    docker push $IMAGE_URL
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Create a temporary Cloud Run job to run migrations
    gcloud run jobs create weather-db-migrate \
        --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest \
        --region=$REGION \
        --set-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
        --set-env-vars="DB_HOST=/cloudsql/$INSTANCE_CONNECTION_NAME,DB_PORT=5432,DB_NAME=weather_db,DB_USER=weather_user" \
        --set-secrets="DB_PASSWORD=weather-db-password:latest" \
        --service-account=weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com \
        --command="python" \
        --args="-c" \
        --args="import psycopg2; conn = psycopg2.connect(host='$DB_HOST', port=5432, database='weather_db', user='weather_user', password='$DB_PASSWORD'); cur = conn.cursor(); cur.execute(open('/app/../postgres/init.sql').read()); conn.commit(); conn.close(); print('Migrations completed')" \
        --project=$PROJECT_ID || true
    
    # Execute the job
    gcloud run jobs execute weather-db-migrate \
        --region=$REGION \
        --project=$PROJECT_ID || true
}

# Deploy to Cloud Run
deploy_cloud_run() {
    print_status "Deploying to Cloud Run..."
    
    gcloud run deploy weather-dashboard \
        --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard:latest \
        --platform=managed \
        --region=$REGION \
        --allow-unauthenticated \
        --set-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
        --set-env-vars="DB_HOST=/cloudsql/$INSTANCE_CONNECTION_NAME,DB_PORT=5432,DB_NAME=weather_db,DB_USER=weather_user" \
        --set-secrets="DB_PASSWORD=weather-db-password:latest" \
        --service-account=weather-platform-sa@$PROJECT_ID.iam.gserviceaccount.com \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=1 \
        --max-instances=100 \
        --port=8080 \
        --project=$PROJECT_ID
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe weather-dashboard \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)")
    
    print_status "Deployment completed!"
    echo
    echo "=========================================="
    echo "Weather Platform deployed successfully!"
    echo "Service URL: $SERVICE_URL"
    echo "=========================================="
}

# Create storage bucket
create_storage() {
    print_status "Creating storage bucket..."
    
    BUCKET_NAME="${PROJECT_ID}-weather-data"
    
    if ! gsutil ls -b gs://$BUCKET_NAME &> /dev/null; then
        gsutil mb -l $REGION gs://$BUCKET_NAME
        
        # Set lifecycle rules
        cat > /tmp/lifecycle.json <<EOF
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
        gsutil lifecycle set /tmp/lifecycle.json gs://$BUCKET_NAME
        rm /tmp/lifecycle.json
    else
        print_warning "Storage bucket already exists"
    fi
    
    # Upload CSV files if they exist
    if [ -d "RAW_DATA" ] && [ "$(ls -A RAW_DATA/*.csv 2>/dev/null)" ]; then
        print_status "Uploading CSV files..."
        gsutil -m cp RAW_DATA/*.csv gs://$BUCKET_NAME/raw/
    fi
}

# Main deployment flow
main() {
    print_status "Starting Weather Platform deployment to GCP..."
    
    check_requirements
    get_config
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    enable_apis
    create_artifact_registry
    create_cloud_sql
    create_service_account
    create_secrets
    build_and_push_image
    run_migrations
    deploy_cloud_run
    create_storage
    
    print_status "Deployment completed successfully!"
    
    # Print next steps
    echo
    echo "Next steps:"
    echo "1. Visit your application at: $SERVICE_URL"
    echo "2. Upload CSV files to gs://${PROJECT_ID}-weather-data/raw/"
    echo "3. Run the ETL process from the dashboard or set up a Cloud Function"
    echo "4. Configure monitoring and alerts in Cloud Console"
}

# Run main function
main