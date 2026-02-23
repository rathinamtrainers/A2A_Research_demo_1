#!/usr/bin/env bash
# deploy_cloud_run.sh — Deploy all A2A agent servers to Google Cloud Run.
#
# Usage:
#   ./scripts/deploy_cloud_run.sh [agent_name]
#
# Examples:
#   ./scripts/deploy_cloud_run.sh               # Deploy all agents
#   ./scripts/deploy_cloud_run.sh weather_agent # Deploy only weather_agent
#
# Prerequisites:
#   - gcloud CLI authenticated: gcloud auth login
#   - Project set: gcloud config set project <PROJECT_ID>
#   - APIs enabled (see ENV_SETUP.md)
#   - .env populated with GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION

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
TARGET="${1:-all}"

echo "=== Cloud Run Deployment ==="
echo "  Project : ${PROJECT}"
echo "  Region  : ${REGION}"
echo "  Target  : ${TARGET}"
echo ""

deploy_agent() {
    local agent_name="$1"
    local service_name="${agent_name//_/-}"  # weather_agent → weather-agent

    echo "  Deploying ${agent_name} as ${service_name}..."
    gcloud run deploy "${service_name}" \
        --source "${PROJECT_ROOT}/${agent_name}" \
        --region "${REGION}" \
        --project "${PROJECT}" \
        --allow-unauthenticated \
        --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=1" \
        --quiet

    # Get the deployed URL
    local url
    url=$(gcloud run services describe "${service_name}" \
        --region "${REGION}" \
        --project "${PROJECT}" \
        --format "value(status.url)")
    echo "  ✓ ${agent_name} → ${url}"
    echo "      Verify: curl ${url}/.well-known/agent.json"
}

AGENTS=("weather_agent" "research_agent" "code_agent" "data_agent" "async_agent" "webhook_server")

if [[ "${TARGET}" == "all" ]]; then
    for agent in "${AGENTS[@]}"; do
        deploy_agent "${agent}"
    done
else
    deploy_agent "${TARGET}"
fi

echo ""
echo "=== Deployment complete ==="
echo "Update your .env with the Cloud Run service URLs."
