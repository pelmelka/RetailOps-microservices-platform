#!/bin/sh

set -eu

namespace="${1:?namespace is required}"

if [ -n "${K8S_REGISTRY_USER:-}" ] || [ -n "${K8S_REGISTRY_PASSWORD:-}" ]; then
  registry_user="${K8S_REGISTRY_USER:?K8S_REGISTRY_USER and K8S_REGISTRY_PASSWORD must be set together}"
  registry_password="${K8S_REGISTRY_PASSWORD:?K8S_REGISTRY_USER and K8S_REGISTRY_PASSWORD must be set together}"
else
  registry_user="${CI_REGISTRY_USER:?CI_REGISTRY_USER is required}"
  registry_password="${CI_REGISTRY_PASSWORD:?CI_REGISTRY_PASSWORD is required}"
fi

kubectl create secret docker-registry gitlab-registry \
  --docker-server="$CI_REGISTRY" \
  --docker-username="$registry_user" \
  --docker-password="$registry_password" \
  --namespace "$namespace" \
  --dry-run=client -o yaml | kubectl apply -f -
