#!/bin/sh

set -eu

if [ -n "${KUBE_CONFIG_B64:-}" ]; then
  kube_dir="${CI_PROJECT_DIR:-$(pwd)}/.kube"
  mkdir -p "$kube_dir"
  printf '%s' "$KUBE_CONFIG_B64" | base64 -d > "$kube_dir/config"
  chmod 600 "$kube_dir/config"
  export KUBECONFIG="$kube_dir/config"
fi
