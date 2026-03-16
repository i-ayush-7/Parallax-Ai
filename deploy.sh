#!/bin/bash
# deploy.sh — One-command deployment of Parallax AI backend to Google Cloud Run
# Usage: ./deploy.sh [PROJECT_ID] [REGION]
# Example: ./deploy.sh my-gcp-project us-central1

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${2:-us-central1}"
SERVICE_NAME="parallax-ai"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# ── Validation ───────────────────────────────────────────────────────────────
if [ -z "$PROJECT_ID" ]; then
  echo "ERROR: No GCP project ID found."
  echo "Usage: ./deploy.sh YOUR_PROJECT_ID"
  exit 1
fi

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "ERROR: GEMINI_API_KEY environment variable is not set."
  echo "Run: export GEMINI_API_KEY=your_key_here"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        Parallax AI — Cloud Run Deploy        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  Service : $SERVICE_NAME"
echo "  Image   : $IMAGE"
echo ""

# ── Step 1: Enable required APIs ─────────────────────────────────────────────
echo "[1/5] Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

echo "      ✓ APIs enabled"

# ── Step 2: Store API key in Secret Manager ───────────────────────────────────
echo "[2/5] Storing GEMINI_API_KEY in Secret Manager..."

# Create secret if it doesn't exist
if ! gcloud secrets describe gemini-api-key --project="$PROJECT_ID" &>/dev/null; then
  gcloud secrets create gemini-api-key \
    --replication-policy="automatic" \
    --project="$PROJECT_ID"
  echo "      ✓ Secret created"
else
  echo "      ✓ Secret already exists"
fi

# Add new version with current key value
echo -n "$GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key \
  --data-file=- \
  --project="$PROJECT_ID"
echo "      ✓ Secret version added"

# ── Step 3: Build container image ────────────────────────────────────────────
echo "[3/5] Building container image..."
gcloud builds submit \
  --tag "$IMAGE" \
  --project="$PROJECT_ID" \
  --quiet
echo "      ✓ Image built and pushed: $IMAGE"

# ── Step 4: Deploy to Cloud Run ──────────────────────────────────────────────
echo "[4/5] Deploying to Cloud Run..."

# Get the Secret Manager service account so we can grant access
CLOUD_RUN_SA="$(gcloud projects describe "$PROJECT_ID" \
  --format='value(projectNumber)')"-compute@developer.gserviceaccount.com

# Grant the service account access to the secret
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${CLOUD_RUN_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || true

gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 3600 \
  --port 8080 \
  --project="$PROJECT_ID" \
  --quiet

echo "      ✓ Deployment complete"

# ── Step 5: Get the service URL ───────────────────────────────────────────────
echo "[5/5] Fetching service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              Deployment complete!            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Service URL: $SERVICE_URL"
echo ""
echo "  Update your frontend WebSocket URL to:"
echo "  wss://${SERVICE_URL#https://}/ws"
echo ""
echo "  To check logs:"
echo "  gcloud run services logs read $SERVICE_NAME --region $REGION"
echo ""
