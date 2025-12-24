# Kubernetes and Helm

## Helm chart

Chart расположен в:

```text
charts/retailops-microservices-platform
```

Основные файлы:

```text
Chart.yaml
values.yaml
values.test.yaml
values.prod.yaml
templates/
```

## Kubernetes resources

Chart создаёт:

| Resource | Компоненты |
|---|---|
| Deployment | api-gateway, backend-сервисы, workflow-service, frontend-dashboard, mailpit |
| StatefulSet | postgres, redis |
| Service | HTTP/SMTP/database endpoints внутри namespace |
| ConfigMap | общая конфигурация и service URLs |
| Secret | JWT secret, database URL, PostgreSQL password |
| PVC | document storage |
| Job | database bootstrap |
| Ingress | внешний HTTP entrypoint |

## Values model

`values.yaml` содержит базовые настройки chart-а.

`values.test.yaml` задаёт test profile:

```text
environment: test
frontend replicas: 1
api-gateway replicas: 1
ingress.enabled: true
```

`values.prod.yaml` задаёт prod profile:

```text
environment: prod
frontend replicas: 2
api-gateway replicas: 2
backend service replicas: 2 for stateless services
larger PostgreSQL/Redis/document storage sizes
```

## Image model

Каждый сервис имеет отдельный image repository и tag:

```yaml
images:
  apiGateway:
    repository: api-gateway
    tag: local
  authService:
    repository: auth-service
    tag: local
  frontendDashboard:
    repository: frontend-dashboard
    tag: local
```

CI/CD подставляет tag только для сервисов, изменённых в текущем наборе изменений.

## Deploy command

```bash
helm upgrade --install retailops charts/retailops-microservices-platform \
  --namespace test \
  --create-namespace \
  -f charts/retailops-microservices-platform/values.test.yaml \
  --set-string global.imageRegistry="$IMAGE_REGISTRY" \
  --set-string global.imagePullSecrets[0].name=gitlab-registry \
  --atomic \
  --wait \
  --timeout 10m
```

Для production меняются namespace и values-файл:

```bash
helm upgrade --install retailops charts/retailops-microservices-platform \
  --namespace prod \
  --create-namespace \
  -f charts/retailops-microservices-platform/values.prod.yaml \
  --set-string global.imageRegistry="$IMAGE_REGISTRY" \
  --set-string global.imagePullSecrets[0].name=gitlab-registry \
  --atomic \
  --wait \
  --timeout 10m
```

## Registry secret

Скрипт `scripts/gitlab-ci/ensure_registry_secret.sh` создаёт или обновляет docker-registry secret в нужном namespace.

Secret name по умолчанию:

```text
gitlab-registry
```

## Bootstrap Job

Bootstrap Job использует backend image и запускает:

```text
python scripts/db/bootstrap_local_db.py
```

Job применяет Alembic migrations и seed-данные.
