#!/bin/sh

set -eu

environment="${1:?environment is required}"
namespace="${2:?namespace is required}"
release="${3:?release is required}"
values_file="${4:?values file is required}"
chart_path="${HELM_CHART_PATH:-charts/retailops-microservices-platform}"
registry_secret_name="${REGISTRY_SECRET_NAME:-gitlab-registry}"
helm_timeout="${HELM_TIMEOUT:-10m}"

if [ "${HAS_DEPLOY_CHANGES:-false}" != "true" ]; then
  echo "No deploy-relevant changes. Skipping Helm deployment for $environment."
  exit 0
fi

image_registry="${IMAGE_REGISTRY:-${CI_REGISTRY_IMAGE:-}}"
if [ -z "$image_registry" ]; then
  echo "IMAGE_REGISTRY or CI_REGISTRY_IMAGE is required" >&2
  exit 1
fi

escape_helm_value() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/,/\\,/g'
}

print_shell_arg() {
  escaped_arg="$(printf '%s' "$1" | sed "s/'/'\\''/g")"
  printf " '%s'" "$escaped_arg"
}

print_helm_command() {
  printf 'Helm command:'
  for arg do
    case "$arg" in
      appSecrets.jwtSecretKey=*)
        print_shell_arg "appSecrets.jwtSecretKey=<redacted>"
        ;;
      postgres.auth.password=*)
        print_shell_arg "postgres.auth.password=<redacted>"
        ;;
      *)
        print_shell_arg "$arg"
        ;;
    esac
  done
  printf '\n'
}

kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
sh scripts/gitlab-ci/ensure_registry_secret.sh "$namespace"

set -- helm upgrade --install "$release" "$chart_path" \
  -f "$values_file" \
  --namespace "$namespace" \
  --create-namespace \
  --atomic \
  --wait \
  --timeout "$helm_timeout" \
  --set-string "global.imageRegistry=$image_registry" \
  --set-string "global.imagePullSecrets[0].name=$registry_secret_name"

if [ -n "${MWP_JWT_SECRET_KEY:-}" ]; then
  jwt_secret="$(escape_helm_value "$MWP_JWT_SECRET_KEY")"
  set -- "$@" --set-string "appSecrets.jwtSecretKey=$jwt_secret"
fi

if [ -n "${MWP_POSTGRES_PASSWORD:-}" ]; then
  postgres_password="$(escape_helm_value "$MWP_POSTGRES_PASSWORD")"
  set -- "$@" --set-string "postgres.auth.password=$postgres_password"
fi

ingress_host=""
case "$environment" in
  test) ingress_host="${TEST_INGRESS_HOST:-}" ;;
  prod) ingress_host="${PROD_INGRESS_HOST:-}" ;;
  *)
    echo "Unsupported environment: $environment" >&2
    exit 1
    ;;
esac

if [ -n "$ingress_host" ]; then
  set -- "$@" --set-string "ingress.host=$(escape_helm_value "$ingress_host")"
fi

helm_args_file="${HELM_SET_ARGS_FILE:-artifacts/helm-set-args.txt}"
if [ -f "$helm_args_file" ]; then
  while IFS=' ' read -r option value; do
    if [ -n "${option:-}" ] && [ -n "${value:-}" ]; then
      set -- "$@" "$option" "$value"
    fi
  done < "$helm_args_file"
fi

echo "Deploying environment=$environment namespace=$namespace release=$release"
print_helm_command "$@"

"$@"
