#!/bin/sh

set -eu

changed_images="${CHANGED_IMAGES:-}"
if [ -z "$changed_images" ]; then
  echo "No changed service images. Nothing to build or push."
  exit 0
fi

docker info
printf '%s' "$CI_REGISTRY_PASSWORD" |
  docker login "$CI_REGISTRY" -u "$CI_REGISTRY_USER" --password-stdin

for service in $(printf '%s' "$changed_images" | tr ',' ' '); do
  image="$CI_REGISTRY_IMAGE/$service:$CI_COMMIT_SHORT_SHA"

  if [ "$service" = "frontend-dashboard" ]; then
    docker build \
      -f deploy/docker/frontend-dashboard.Dockerfile \
      -t "$image" \
      .
  else
    case "$service" in
      api-gateway) service_module="api_gateway.main:app" ;;
      auth-service) service_module="auth_service.main:app" ;;
      catalog-service) service_module="catalog_service.main:app" ;;
      order-service) service_module="order_service.main:app" ;;
      payment-service) service_module="payment_service.main:app" ;;
      document-service) service_module="document_service.main:app" ;;
      notification-service) service_module="notification_service.main:app" ;;
      workflow-service) service_module="workflow_service.main:app" ;;
      *)
        echo "Unsupported service image: $service" >&2
        exit 1
        ;;
    esac

    docker build \
      -f deploy/docker/backend-service.Dockerfile \
      --build-arg "SERVICE_PATH=services/$service" \
      --build-arg "SERVICE_MODULE=$service_module" \
      -t "$image" \
      .
  fi

  docker push "$image"
done
