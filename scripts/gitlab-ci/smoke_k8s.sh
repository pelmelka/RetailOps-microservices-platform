#!/bin/sh

set -eu

namespace="${1:?namespace is required}"

if [ "${HAS_DEPLOY_CHANGES:-false}" != "true" ]; then
  echo "No deploy-relevant changes. Skipping Kubernetes smoke checks."
  exit 0
fi

kubectl get pods -n "$namespace"
kubectl get svc -n "$namespace"
kubectl get ingress -n "$namespace"

rollout_if_present() {
  resource="$1"
  if kubectl get "$resource" -n "$namespace" >/dev/null 2>&1; then
    kubectl rollout status "$resource" -n "$namespace" --timeout=5m
  fi
}

changed_services="${CHANGED_SERVICES:-}"
if [ "${HAS_CHART_CHANGES:-false}" = "true" ]; then
  for deployment in \
    api-gateway \
    auth-service \
    catalog-service \
    order-service \
    payment-service \
    document-service \
    notification-service \
    workflow-service \
    frontend-dashboard \
    mailpit
  do
    rollout_if_present "deployment/$deployment"
  done
  rollout_if_present statefulset/postgres
  rollout_if_present statefulset/redis
elif [ -n "$changed_services" ]; then
  for service in $(printf '%s' "$changed_services" | tr ',' ' '); do
    rollout_if_present "deployment/$service"
  done
else
  rollout_if_present deployment/api-gateway
  rollout_if_present deployment/frontend-dashboard
fi

case ",$changed_services," in
  *,api-gateway,*|*,auth-service,*|*,catalog-service,*|*,order-service,*|*,payment-service,*|*,document-service,*|*,notification-service,*|*,workflow-service,*)
    kubectl delete pod smoke-api-test -n "$namespace" --ignore-not-found=true
    kubectl run smoke-api-test \
      --rm -i --restart=Never \
      --image=curlimages/curl:8.8.0 \
      --namespace="$namespace" \
      --command -- sh -c "curl -fsS http://api-gateway:8000/api/catalog/items"
    ;;
  *)
    if [ "${HAS_CHART_CHANGES:-false}" = "true" ]; then
      kubectl delete pod smoke-api-test -n "$namespace" --ignore-not-found=true
      kubectl run smoke-api-test \
        --rm -i --restart=Never \
        --image=curlimages/curl:8.8.0 \
        --namespace="$namespace" \
        --command -- sh -c "curl -fsS http://api-gateway:8000/api/catalog/items"
    fi
    ;;
esac

case ",$changed_services," in
  *,frontend-dashboard,*)
    kubectl delete pod smoke-frontend-test -n "$namespace" --ignore-not-found=true
    kubectl run smoke-frontend-test \
      --rm -i --restart=Never \
      --image=curlimages/curl:8.8.0 \
      --namespace="$namespace" \
      --command -- sh -c "curl -fsS http://frontend-dashboard:3000/"
    ;;
  *)
    if [ "${HAS_CHART_CHANGES:-false}" = "true" ]; then
      kubectl delete pod smoke-frontend-test -n "$namespace" --ignore-not-found=true
      kubectl run smoke-frontend-test \
        --rm -i --restart=Never \
        --image=curlimages/curl:8.8.0 \
        --namespace="$namespace" \
        --command -- sh -c "curl -fsS http://frontend-dashboard:3000/"
    fi
    ;;
esac
