# Runtime and deployment

## Локальный runtime

Docker Compose профиль поднимает:

```text
api-gateway
auth-service
catalog-service
order-service
payment-service
document-service
notification-service
workflow-service
frontend-dashboard
postgres
redis
mailpit
```

Запуск:

```bash
docker compose -f deploy/docker-compose/docker-compose.yml --env-file deploy/docker-compose/.env.example up --build -d
```

Bootstrap базы:

```bash
export DATABASE_URL="postgresql+asyncpg://retailops:retailops_local_password@localhost:5432/retailops"
python scripts/db/bootstrap_local_db.py
```

Smoke:

```bash
python scripts/smoke/check_async_workflow.py
```

Остановка:

```bash
docker compose -f deploy/docker-compose/docker-compose.yml --env-file deploy/docker-compose/.env.example down
```

## Kubernetes runtime

Kubernetes-профиль описан Helm chart-ом:

```text
charts/retailops-microservices-platform
```

Для окружений используются namespaces:

```text
test
prod
```

Deploy test:

```bash
helm upgrade --install retailops charts/retailops-microservices-platform \
  --namespace test \
  --create-namespace \
  -f charts/retailops-microservices-platform/values.test.yaml \
  --atomic \
  --wait \
  --timeout 10m
```

Deploy prod:

```bash
helm upgrade --install retailops charts/retailops-microservices-platform \
  --namespace prod \
  --create-namespace \
  -f charts/retailops-microservices-platform/values.prod.yaml \
  --atomic \
  --wait \
  --timeout 10m
```

## Проверка после развёртывания

```bash
kubectl get pods -n test
kubectl get svc -n test
kubectl get ingress -n test
kubectl rollout status deployment/api-gateway -n test --timeout=5m
kubectl rollout status deployment/frontend-dashboard -n test --timeout=5m
```

Проверка API внутри namespace:

```bash
kubectl run smoke-api-test \
  --rm -i --restart=Never \
  --image=curlimages/curl:8.8.0 \
  --namespace=test \
  --command -- sh -c "curl -fsS http://api-gateway:8000/api/catalog/items"
```
