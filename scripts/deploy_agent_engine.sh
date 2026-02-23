#!/usr/bin/env bash
# deploy_agent_engine.sh — Deploy orchestrator_agent to Vertex AI Agent Engine.
#
# Reference: F19 — Vertex AI Agent Engine Deployment.
#
# Usage:
#   ./scripts/deploy_agent_engine.sh
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Vertex AI API enabled
#   - VERTEXAI_STAGING_BUCKET set in .env
#   - All remote agents deployed to Cloud Run and URLs updated in .env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set in .env}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
BUCKET="${VERTEXAI_STAGING_BUCKET:?VERTEXAI_STAGING_BUCKET must be set in .env}"
DISPLAY_NAME="a2a-demo-orchestrator"

echo "=== Vertex AI Agent Engine Deployment ==="
echo "  Project  : ${PROJECT}"
echo "  Region   : ${REGION}"
echo "  Bucket   : ${BUCKET}"
echo "  Name     : ${DISPLAY_NAME}"
echo ""

# Ensure the staging bucket exists
echo "  Ensuring staging bucket exists..."
gcloud storage buckets describe "${BUCKET}" --project "${PROJECT}" > /dev/null 2>&1 || \
    gcloud storage buckets create "${BUCKET}" \
        --location "${REGION}" \
        --project "${PROJECT}"
echo "  ✓ Bucket ready: ${BUCKET}"

# Deploy using ADK CLI
echo "  Running: adk deploy agent_engine ..."
cd "${PROJECT_ROOT}"
.venv/bin/adk deploy agent_engine \
    --project "${PROJECT}" \
    --region "${REGION}" \
    --display_name "${DISPLAY_NAME}" \
    --staging_bucket "${BUCKET}" \
    ./orchestrator_agent/

echo ""
echo "=== Agent Engine deployment initiated ==="
echo "Monitor progress in the Google Cloud Console:"
echo "  https://console.cloud.google.com/vertex-ai/agents?project=${PROJECT}"
