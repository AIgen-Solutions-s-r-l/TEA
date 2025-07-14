# GKE (Google Kubernetes Engine) Deployment Guide

## Architecture Overview

```
┌──────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Load Balancer    │────▶│   GKE Cluster   │────▶│  Cloud SQL      │
│ (Ingress)        │     │                 │     │  (PostgreSQL)   │
└──────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                         ┌─────┴─────┐
                         ▼           ▼
                  ┌──────────┐ ┌──────────┐
                  │Dashboard │ │   ETL    │
                  │   Pods   │ │   Jobs   │
                  └──────────┘ └──────────┘
```

## Step 1: Create GKE Cluster

```bash
# Set variables
export CLUSTER_NAME=weather-platform-cluster
export ZONE=europe-west1-b

# Create GKE cluster
gcloud container clusters create $CLUSTER_NAME \
    --zone=$ZONE \
    --num-nodes=3 \
    --machine-type=e2-standard-4 \
    --enable-autoscaling \
    --min-nodes=2 \
    --max-nodes=10 \
    --enable-autorepair \
    --enable-autoupgrade \
    --release-channel=regular \
    --network=default \
    --enable-ip-alias \
    --enable-stackdriver-kubernetes \
    --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver

# Get credentials
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE
```

## Step 2: Create Kubernetes Resources

### Namespace
```yaml
# deployment/gcp/k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: weather-platform
```

### ConfigMap
```yaml
# deployment/gcp/k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: weather-config
  namespace: weather-platform
data:
  DB_HOST: "127.0.0.1"  # Using Cloud SQL Proxy
  DB_PORT: "5432"
  DB_NAME: "weather_db"
  DB_USER: "weather_user"
```

### Secret
```yaml
# deployment/gcp/k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: weather-secrets
  namespace: weather-platform
type: Opaque
stringData:
  db-password: "your-secure-password"
```

### Deployment
```yaml
# deployment/gcp/k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weather-dashboard
  namespace: weather-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: weather-dashboard
  template:
    metadata:
      labels:
        app: weather-dashboard
    spec:
      serviceAccountName: weather-ksa
      containers:
      - name: dashboard
        image: REGION-docker.pkg.dev/PROJECT_ID/weather-platform/dashboard:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: weather-config
              key: DB_HOST
        - name: DB_PORT
          valueFrom:
            configMapKeyRef:
              name: weather-config
              key: DB_PORT
        - name: DB_NAME
          valueFrom:
            configMapKeyRef:
              name: weather-config
              key: DB_NAME
        - name: DB_USER
          valueFrom:
            configMapKeyRef:
              name: weather-config
              key: DB_USER
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: weather-secrets
              key: db-password
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /_stcore/health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /_stcore/health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      
      # Cloud SQL Proxy sidecar
      - name: cloud-sql-proxy
        image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.8.0
        args:
          - "--private-ip"
          - "--structured-logs"
          - "--port=5432"
          - "PROJECT_ID:REGION:weather-db"
        securityContext:
          runAsNonRoot: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
```

### Service
```yaml
# deployment/gcp/k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: weather-dashboard-service
  namespace: weather-platform
spec:
  selector:
    app: weather-dashboard
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer
```

### Horizontal Pod Autoscaler
```yaml
# deployment/gcp/k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: weather-dashboard-hpa
  namespace: weather-platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weather-dashboard
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### ETL CronJob
```yaml
# deployment/gcp/k8s/etl-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: weather-etl
  namespace: weather-platform
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: weather-ksa
          containers:
          - name: etl
            image: REGION-docker.pkg.dev/PROJECT_ID/weather-platform/dashboard:latest
            command: ["python", "/app/etl/load_csv_to_pg.py"]
            env:
            - name: DB_HOST
              value: "127.0.0.1"
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: weather-secrets
                  key: db-password
            volumeMounts:
            - name: data
              mountPath: /data
          
          - name: cloud-sql-proxy
            image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.8.0
            args:
              - "--private-ip"
              - "PROJECT_ID:REGION:weather-db"
          
          volumes:
          - name: data
            emptyDir: {}
          
          initContainers:
          - name: download-data
            image: google/cloud-sdk:alpine
            command:
            - sh
            - -c
            - |
              gsutil -m cp gs://PROJECT_ID-weather-data/raw/*.csv /data/
            volumeMounts:
            - name: data
              mountPath: /data
          
          restartPolicy: OnFailure
```

## Step 3: Set up Workload Identity

```bash
# Create Google Service Account
gcloud iam service-accounts create weather-gke-sa \
    --display-name="Weather GKE Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:weather-gke-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:weather-gke-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Create Kubernetes Service Account
kubectl create serviceaccount weather-ksa -n weather-platform

# Bind the accounts
gcloud iam service-accounts add-iam-policy-binding \
    weather-gke-sa@$PROJECT_ID.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:$PROJECT_ID.svc.id.goog[weather-platform/weather-ksa]"

# Annotate KSA
kubectl annotate serviceaccount weather-ksa \
    -n weather-platform \
    iam.gke.io/gcp-service-account=weather-gke-sa@$PROJECT_ID.iam.gserviceaccount.com
```

## Step 4: Deploy Using Helm (Optional)

```yaml
# deployment/gcp/helm/weather-platform/Chart.yaml
apiVersion: v2
name: weather-platform
description: Weather Data Platform Helm chart
type: application
version: 0.1.0
appVersion: "1.0"
```

```yaml
# deployment/gcp/helm/weather-platform/values.yaml
replicaCount: 3

image:
  repository: REGION-docker.pkg.dev/PROJECT_ID/weather-platform/dashboard
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: weather.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: weather-tls
      hosts:
        - weather.example.com

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

postgresql:
  enabled: false  # Using Cloud SQL
  
cloudSqlProxy:
  enabled: true
  connectionName: "PROJECT_ID:REGION:weather-db"
```

## Step 5: Deploy

```bash
# Apply all configurations
kubectl apply -f deployment/gcp/k8s/

# Or using Helm
helm install weather-platform deployment/gcp/helm/weather-platform \
    --namespace weather-platform \
    --create-namespace \
    --set image.repository=${REGION}-docker.pkg.dev/${PROJECT_ID}/weather-platform/dashboard

# Check deployment status
kubectl get all -n weather-platform

# Get external IP
kubectl get service weather-dashboard-service -n weather-platform
```

## Step 6: Set up Monitoring

```yaml
# deployment/gcp/k8s/monitoring.yaml
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: weather-dashboard-monitor
  namespace: weather-platform
spec:
  selector:
    matchLabels:
      app: weather-dashboard
  endpoints:
  - port: metrics
    interval: 30s
```

## Step 7: Configure Backup

```bash
# Install Velero for backup
velero install \
    --provider gcp \
    --plugins velero/velero-plugin-for-gcp:v1.8.0 \
    --bucket $PROJECT_ID-velero-backup \
    --secret-file ./credentials-velero

# Create backup schedule
velero schedule create weather-daily \
    --schedule="0 2 * * *" \
    --include-namespaces weather-platform
```

## Best Practices

1. **Use Network Policies** for pod-to-pod communication
2. **Enable Pod Security Standards**
3. **Use Kubernetes Secrets with Google Secret Manager**
4. **Implement proper resource quotas**
5. **Use GKE Autopilot** for simplified management

```yaml
# Network Policy example
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: weather-network-policy
  namespace: weather-platform
spec:
  podSelector:
    matchLabels:
      app: weather-dashboard
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: weather-dashboard
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: cloud-sql-proxy
    ports:
    - protocol: TCP
      port: 5432
```