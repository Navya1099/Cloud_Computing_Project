# GCP Deployment Guide for Travel Expense Optimizer

## Prerequisites

1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
2. A GCP account with billing enabled
3. Your Amadeus API credentials

## Step 1: Initial GCP Setup

```bash
# Login to GCP
gcloud auth login

# Create a new project (or use existing)
gcloud projects create travel-expense-optimizer --name="Travel Expense Optimizer"

# Set the project as default
gcloud config set project travel-expense-optimizer

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

## Step 2: Set Up Firestore Database

```bash
# Create Firestore database in Native mode
gcloud firestore databases create --location=europe-west2
```

## Step 3: Store Secrets in Secret Manager

```bash
# Create secrets for your API keys
echo -n "YOUR_AMADEUS_API_KEY" | gcloud secrets create amadeus-api-key --data-file=-
echo -n "YOUR_AMADEUS_API_SECRET" | gcloud secrets create amadeus-api-secret --data-file=-
echo -n "your-super-secret-flask-key-change-this" | gcloud secrets create flask-secret-key --data-file=-

# Grant Cloud Run access to secrets
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding amadeus-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding amadeus-api-secret \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding flask-secret-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Step 4: Deploy to Cloud Run

### Option A: Using Cloud Build (Recommended)

```bash
# Submit build and deploy
cd /path/to/TravelExpenseOptimizer
gcloud builds submit --config=cloudbuild.yaml
```

### Option B: Manual Deployment

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/travel-expense-optimizer

# Deploy to Cloud Run
gcloud run deploy travel-expense-optimizer \
    --image gcr.io/$(gcloud config get-value project)/travel-expense-optimizer \
    --platform managed \
    --region europe-west2 \
    --allow-unauthenticated \
    --set-env-vars USE_FIRESTORE=true \
    --set-secrets AMADEUS_API_KEY=amadeus-api-key:latest,AMADEUS_API_SECRET=amadeus-api-secret:latest,SECRET_KEY=flask-secret-key:latest
```

## Step 5: Access Your App

After deployment, you'll get a URL like:
```
https://travel-expense-optimizer-xxxxx-nw.a.run.app
```

## Local Development

For local development, the app uses in-memory storage by default:

```bash
# Create .env file
cat > .env << EOF
AMADEUS_API_KEY=your_api_key
AMADEUS_API_SECRET=your_api_secret
SECRET_KEY=local-dev-secret-key
USE_FIRESTORE=false
EOF

# Run locally
python app.py
```

## Updating the App

After making changes:

```bash
# Redeploy
gcloud builds submit --config=cloudbuild.yaml
```

## Monitoring & Logs

```bash
# View logs
gcloud run services logs read travel-expense-optimizer --region europe-west2

# Open Cloud Console for monitoring
gcloud run services describe travel-expense-optimizer --region europe-west2 --format='value(status.url)'
```

## Cost Estimation

- **Cloud Run**: Free tier includes 2 million requests/month
- **Firestore**: Free tier includes 1GB storage, 50K reads/day
- **Secret Manager**: Free tier includes 10,000 access operations/month

For a small project, this should stay within free tier limits.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐
│   User Browser  │────▶│    Cloud Run     │
└─────────────────┘     │  (Flask App)     │
                        └────────┬─────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│    Firestore     │  │  Secret Manager  │  │   Amadeus API    │
│   (User Data)    │  │   (API Keys)     │  │  (Travel Data)   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```
