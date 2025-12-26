# Demo guide

## 1. Показ репозитория

Показать структуру:

```text
services/
packages/shared/
deploy/docker-compose/
charts/retailops-microservices-platform/
scripts/gitlab-ci/
scripts/smoke/
docs/
```

## 2. Локальная проверка

```bash
docker compose -f deploy/docker-compose/docker-compose.yml --env-file deploy/docker-compose/.env.example up --build -d
export DATABASE_URL="postgresql+asyncpg://retailops:retailops_local_password@localhost:5432/retailops"
python scripts/db/bootstrap_local_db.py
python scripts/smoke/check_async_workflow.py
```

Открыть dashboard:

```text
http://localhost:3000
```

Показать Mailpit:

```text
http://localhost:8025
```

## 3. Helm chart

```bash
helm lint charts/retailops-microservices-platform
helm template retailops-test charts/retailops-microservices-platform -f charts/retailops-microservices-platform/values.test.yaml --namespace test
```

Показать templates:

```text
deployment
service
statefulset
configmap
secret
pvc
ingress
bootstrap job
```

## 4. CI/CD flow

Показать `.gitlab-ci.yml`:

```text
validate
build
deploy_test
smoke_test
deploy_prod
smoke_prod
```

Показать scripts:

```text
detect_changed_artifacts.sh
build_changed_images.sh
deploy_helm.sh
smoke_k8s.sh
```

## 5. Kubernetes state

```bash
kubectl get pods -n test
kubectl get svc -n test
kubectl get ingress -n test
kubectl rollout status deployment/api-gateway -n test --timeout=5m
```

## 6. Application scenario

Через dashboard:

```text
login/register
catalog
create order
invoice
payment success
receipt
notification
order history
```
