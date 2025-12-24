# CI/CD

## Pipeline stages

```text
validate
build
deploy_test
smoke_test
deploy_prod
smoke_prod
```

## Validate

`detect_changes` формирует артефакты:

```text
artifacts/changed.env
artifacts/changed-files.txt
artifacts/changed-services.txt
artifacts/helm-set-args.txt
```

Остальные validation jobs:

```text
python_compile
pytest
frontend_build
helm_validate
shell_syntax
```

## Build

`build_changed_images` собирает только изменённые сервисы.

Backend-сервисы используют общий Dockerfile:

```text
deploy/docker/backend-service.Dockerfile
```

Frontend использует отдельный Dockerfile:

```text
deploy/docker/frontend-dashboard.Dockerfile
```

Image tag формируется из short commit SHA и подставляется в Helm через `artifacts/helm-set-args.txt`.

## Deploy test

Deploy выполняется скриптом:

```bash
sh scripts/gitlab-ci/deploy_helm.sh test test retailops charts/retailops-microservices-platform/values.test.yaml
```

Скрипт выполняет:

```text
namespace apply
registry secret apply
helm upgrade --install
image registry override
image tag overrides for changed services
JWT/PostgreSQL secret overrides
Ingress host override
atomic wait
```

## Smoke test

Smoke-скрипт проверяет:

```text
pods
services
ingress
rollout status для изменённых deployment/statefulset
api-gateway catalog endpoint
frontend-dashboard root page
```

Команда:

```bash
sh scripts/gitlab-ci/smoke_k8s.sh test
```

## Deploy prod

Production deploy запускается после test smoke:

```bash
sh scripts/gitlab-ci/deploy_helm.sh prod prod retailops charts/retailops-microservices-platform/values.prod.yaml
```

## Required CI/CD variables

```text
KUBE_CONFIG_B64
TEST_INGRESS_HOST
PROD_INGRESS_HOST
MWP_POSTGRES_PASSWORD
MWP_JWT_SECRET_KEY
```

Registry credentials используются из CI runtime. Для отдельного deploy token доступны:

```text
K8S_REGISTRY_USER
K8S_REGISTRY_PASSWORD
```

## Deploy script

Финальная логика deploy-скрипта использует `helm upgrade --install`:

```bash
helm upgrade --install "$release" "$chart_path" \
  -f "$values_file" \
  --namespace "$namespace" \
  --create-namespace \
  --atomic \
  --wait \
  --timeout "$helm_timeout" \
  --set-string "global.imageRegistry=$image_registry" \
  --set-string "global.imagePullSecrets[0].name=$registry_secret_name"
```
