#!/bin/sh

set -eu

artifacts_dir="${ARTIFACTS_DIR:-artifacts}"
state_dir="$artifacts_dir/.change-state"
head_sha="${CI_COMMIT_SHA:-HEAD}"
zero_sha="0000000000000000000000000000000000000000"

rm -rf "$artifacts_dir"
mkdir -p "$state_dir"

resolve_base_sha() {
  candidate=""

  if [ "${CI_PIPELINE_SOURCE:-}" = "merge_request_event" ]; then
    candidate="${CI_MERGE_REQUEST_DIFF_BASE_SHA:-}"
  elif [ -n "${CI_COMMIT_BEFORE_SHA:-}" ] && [ "$CI_COMMIT_BEFORE_SHA" != "$zero_sha" ]; then
    candidate="$CI_COMMIT_BEFORE_SHA"
  fi

  if [ -n "$candidate" ] && git cat-file -e "$candidate^{commit}" 2>/dev/null; then
    printf '%s\n' "$candidate"
    return
  fi

  if [ -n "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-}" ]; then
    candidate="origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    if git cat-file -e "$candidate^{commit}" 2>/dev/null; then
      git merge-base "$candidate" "$head_sha"
      return
    fi
  fi

  if git rev-parse "$head_sha^" >/dev/null 2>&1; then
    git rev-parse "$head_sha^"
  fi
}

base_sha="$(resolve_base_sha)"
if [ -n "$base_sha" ]; then
  git diff --name-only "$base_sha" "$head_sha" | sort -u > "$artifacts_dir/changed-files.txt"
else
  git ls-tree -r --name-only "$head_sha" | sort -u > "$artifacts_dir/changed-files.txt"
fi

add_service() {
  touch "$state_dir/service-$1"
  touch "$state_dir/image-changes"
  touch "$state_dir/deploy-changes"
}

add_all_backend_services() {
  for service in \
    api-gateway \
    auth-service \
    catalog-service \
    order-service \
    payment-service \
    document-service \
    notification-service \
    workflow-service
  do
    add_service "$service"
  done
}

add_all_project_services() {
  add_all_backend_services
  add_service frontend-dashboard
  touch "$state_dir/frontend-changes"
}

while IFS= read -r path; do
  case "$path" in
    services/api-gateway/*) add_service api-gateway ;;
    services/auth-service/*) add_service auth-service ;;
    services/catalog-service/*) add_service catalog-service ;;
    services/order-service/*) add_service order-service ;;
    services/payment-service/*) add_service payment-service ;;
    services/document-service/*) add_service document-service ;;
    services/notification-service/*) add_service notification-service ;;
    services/workflow-service/*) add_service workflow-service ;;
    services/frontend-dashboard/*)
      add_service frontend-dashboard
      touch "$state_dir/frontend-changes"
      ;;
    packages/shared/*|deploy/docker/backend-service.Dockerfile)
      add_all_backend_services
      touch "$state_dir/backend-common-changes"
      ;;
    .dockerignore)
      add_all_project_services
      touch "$state_dir/backend-common-changes"
      ;;
    deploy/docker/frontend-dashboard.Dockerfile)
      add_service frontend-dashboard
      touch "$state_dir/frontend-changes"
      ;;
    alembic.ini|migrations/*|scripts/db/*)
      add_service api-gateway
      ;;
    charts/*|deploy/kubernetes/*|scripts/gitlab-ci/*|.gitlab-ci.yml)
      touch "$state_dir/chart-changes"
      touch "$state_dir/deploy-changes"
      ;;
  esac
done < "$artifacts_dir/changed-files.txt"

: > "$artifacts_dir/changed-services.txt"
: > "$artifacts_dir/helm-set-args.txt"

changed_services=""
helm_set_args=""
image_tag="${CI_COMMIT_SHORT_SHA:-$(git rev-parse --short "$head_sha")}"

for service in \
  api-gateway \
  auth-service \
  catalog-service \
  order-service \
  payment-service \
  document-service \
  notification-service \
  workflow-service \
  frontend-dashboard
do
  if [ ! -f "$state_dir/service-$service" ]; then
    continue
  fi

  printf '%s\n' "$service" >> "$artifacts_dir/changed-services.txt"
  if [ -n "$changed_services" ]; then
    changed_services="$changed_services,$service"
  else
    changed_services="$service"
  fi

  case "$service" in
    api-gateway) image_key="apiGateway" ;;
    auth-service) image_key="authService" ;;
    catalog-service) image_key="catalogService" ;;
    order-service) image_key="orderService" ;;
    payment-service) image_key="paymentService" ;;
    document-service) image_key="documentService" ;;
    notification-service) image_key="notificationService" ;;
    workflow-service) image_key="workflowService" ;;
    frontend-dashboard) image_key="frontendDashboard" ;;
  esac

  helm_value="images.$image_key.tag=$image_tag"
  printf '%s %s\n' "--set-string" "$helm_value" >> "$artifacts_dir/helm-set-args.txt"
  if [ -n "$helm_set_args" ]; then
    helm_set_args="$helm_set_args --set-string $helm_value"
  else
    helm_set_args="--set-string $helm_value"
  fi
done

flag() {
  if [ -f "$state_dir/$1" ]; then
    printf 'true'
  else
    printf 'false'
  fi
}

has_image_changes="$(flag image-changes)"
has_deploy_changes="$(flag deploy-changes)"
has_frontend_changes="$(flag frontend-changes)"
has_backend_common_changes="$(flag backend-common-changes)"
has_chart_changes="$(flag chart-changes)"
has_chart_only_changes="false"
if [ "$has_chart_changes" = "true" ] && [ "$has_image_changes" = "false" ]; then
  has_chart_only_changes="true"
fi

cat > "$artifacts_dir/changed.env" <<EOF
CHANGED_SERVICES=$changed_services
CHANGED_IMAGES=$changed_services
HELM_SET_ARGS=$helm_set_args
HAS_IMAGE_CHANGES=$has_image_changes
HAS_DEPLOY_CHANGES=$has_deploy_changes
HAS_FRONTEND_CHANGES=$has_frontend_changes
HAS_BACKEND_COMMON_CHANGES=$has_backend_common_changes
HAS_CHART_CHANGES=$has_chart_changes
HAS_CHART_ONLY_CHANGES=$has_chart_only_changes
EOF

rm -rf "$state_dir"

printf 'Base SHA: %s\n' "${base_sha:-<full tree>}"
printf 'Changed services: %s\n' "${changed_services:-<none>}"
printf 'Image changes: %s\n' "$has_image_changes"
printf 'Deploy changes: %s\n' "$has_deploy_changes"
