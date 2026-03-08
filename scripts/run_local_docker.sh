#!/usr/bin/env bash

# Script to test Docker build locally before CI/CD deployment
# This mimics the build process used in GitHub Actions

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="my-finance-api-test"
IMAGE_NAME_TAG="${IMAGE_NAME}:latest"
CONTAINER_NAME="${IMAGE_NAME}-local"
PORT=8080
ENV=${ENV:-"dev"}

echo -e "${YELLOW}🐳 Testing Docker build locally${NC}"
echo "Environment: $ENV"

# Check for .env file
if [[ ! -f .env ]]; then
  echo -e "${RED}❌ .env file not found! Please create one according to the README instructions.${NC}"
  exit 1
fi

# Ensure Docker Desktop / daemon is running; open it if not and wait until ready.
ensure_docker_running() {
  local timeout=120
  local interval=2
  local waited=0

  if docker info >/dev/null 2>&1; then
    return 0
  fi

  echo "Docker daemon not available. Opening Docker.app..."
  open -a Docker

  printf "Waiting for Docker to be ready"
  while ! docker info >/dev/null 2>&1; do
    sleep "$interval"
    waited=$((waited + interval))
    printf "."
    if [ "$waited" -ge "$timeout" ]; then
      echo
      echo "Timed out after ${timeout}s waiting for Docker to start."
      return 1
    fi
  done
  echo
  echo "Docker is ready (waited ${waited}s)."
  return 0
}

if ! ensure_docker_running; then
  echo -e "${RED}❌ Cannot connect to Docker daemon. Please start Docker Desktop manually and retry.${NC}"
  exit 1
fi

# Check if authenticated with gcloud
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1 || true)"
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  echo -e "${RED}❌ Not authenticated with gcloud. Run 'gcloud auth login' and 'gcloud auth application-default login' first.${NC}"
  exit 1
fi

echo "Active gcloud account: ${ACTIVE_ACCOUNT}"

# Get current project ID and location from gcloud config
GCP_PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
GCP_LOCATION="$(gcloud config get-value artifacts/location 2>/dev/null || true)"

if [[ -z "${GCP_LOCATION}" || "${GCP_LOCATION}" == "(unset)" ]]; then
  GCP_LOCATION="$(gcloud config get-value compute/region 2>/dev/null || true)"
fi

if [[ -z "${GCP_LOCATION}" || "${GCP_LOCATION}" == "(unset)" ]]; then
  GCP_LOCATION="europe-north1"
fi

if [[ -z "${GCP_PROJECT_ID}" || "${GCP_PROJECT_ID}" == "(unset)" ]]; then
  echo -e "${RED}❌ GCP project not set. Run 'gcloud config set project YOUR_PROJECT_ID'${NC}"
  exit 1
fi

echo "Project: $GCP_PROJECT_ID"
echo "Location: $GCP_LOCATION"

# Generate OAuth token for private registry access during build
echo -e "${YELLOW}🔑 Generating OAuth token for build...${NC}"
GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth application-default print-access-token 2>/dev/null || true)"

if [[ -z "${GOOGLE_OAUTH_ACCESS_TOKEN}" ]]; then
  echo -e "${RED}❌ Failed to get OAuth token. Run 'gcloud auth application-default login'${NC}"
  exit 1
fi

# Create temp file for BuildKit secret
TOKEN_FILE="$(mktemp)"
cleanup() {
  rm -f "${TOKEN_FILE}"
}
trap cleanup EXIT

printf '%s' "${GOOGLE_OAUTH_ACCESS_TOKEN}" > "${TOKEN_FILE}"

# Build Docker image
echo -e "\n${YELLOW}🔨 1. Building Docker image ${IMAGE_NAME_TAG}...${NC}"
DOCKER_BUILDKIT=1 docker build \
  --secret id=oauth_token,src="${TOKEN_FILE}" \
  --build-arg ENV="${ENV}" \
  --build-arg GCP_LOCATION="${GCP_LOCATION}" \
  --build-arg GCP_PROJECT_ID="${GCP_PROJECT_ID}" \
  -t "${IMAGE_NAME_TAG}" \
  .

echo -e "${GREEN}✅ Docker build successful!${NC}"

# Stop and remove any existing container with the same name
if docker ps -aq -f name="^${CONTAINER_NAME}$" | grep -q .; then
  echo -e "\n${YELLOW}🧹 2. Stopping and removing existing container ${CONTAINER_NAME}...${NC}"
  docker rm -f "${CONTAINER_NAME}"
fi

# Runtime ADC path on host
HOST_GCLOUD_CONFIG="${HOME}/.config/gcloud"
HOST_ADC_FILE="${HOST_GCLOUD_CONFIG}/application_default_credentials.json"

if [[ ! -f "${HOST_ADC_FILE}" ]]; then
  echo -e "${RED}❌ Application default credentials not found at:${NC} ${HOST_ADC_FILE}"
  echo "Run: gcloud auth application-default login"
  exit 1
fi

# Run the Docker container
# The Dockerfile switches to user 'app', whose home is /home/app
echo -e "\n${YELLOW}🚀 3. Running container ${CONTAINER_NAME} from image ${IMAGE_NAME_TAG} (port ${PORT})...${NC}"
docker run -d \
  --env-file .env \
  -p "${PORT}:${PORT}" \
  -v "${HOST_GCLOUD_CONFIG}:/home/app/.config/gcloud:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/home/app/.config/gcloud/application_default_credentials.json \
  -e PORT="${PORT}" \
  --name "${CONTAINER_NAME}" \
  "${IMAGE_NAME_TAG}"

echo -e "\n${GREEN}✅ 4. Container ${CONTAINER_NAME} is running. Access the app at http://localhost:${PORT}${NC}"

# Wait a moment and check if container is running
sleep 3
if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo -e "${GREEN}✅ Container is running successfully${NC}"
  echo -e "${YELLOW}📋 Recent logs:${NC}"
  docker logs "${CONTAINER_NAME}" 2>&1 | tail -10
else
  echo -e "${RED}❌ Container failed to start. Check logs:${NC}"
  docker logs "${CONTAINER_NAME}" 2>&1 || true
  exit 1
fi

echo
echo -e "${YELLOW}📝 Useful commands:${NC}"
echo "  View logs: docker logs ${CONTAINER_NAME} -f"
echo "  Stop container: docker stop ${CONTAINER_NAME}"
echo "  Remove container: docker rm -f ${CONTAINER_NAME}"
echo "  Remove test image: docker rmi ${IMAGE_NAME_TAG}"

echo -e "${GREEN}🎉 Docker test completed successfully!${NC}"
