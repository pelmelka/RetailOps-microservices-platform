# Visual assets map

Файл описывает, какие схемы и скриншоты можно добавить в README или портфолио.

## Recommended diagrams

### 1. Kubernetes deployment overview

Показывает:

```text
Ingress
frontend-dashboard
api-gateway
backend services
workflow-service
PostgreSQL
Redis
Mailpit
PVC document storage
```

### 2. CI/CD pipeline

Показывает стадии:

```text
validate
build images
deploy test
smoke test
manual promote
deploy prod
smoke prod
```

### 3. Async workflow

Показывает:

```text
create order
Redis command
order-service
document-service
awaiting payment
payment-service
receipt
notification
completed
```

### 4. Helm chart structure

Показывает:

```text
values.yaml
values.test.yaml
values.prod.yaml
templates/deployments
templates/services
templates/statefulsets
templates/ingress
```

## Recommended screenshots

| Screenshot | Что показать |
|---|---|
| Dashboard main screen | Каталог, заказ, workflow status |
| Order history | История статусов заказа |
| Documents | Invoice/receipt download buttons |
| Mailpit | Email notification |
| Kubernetes pods | `kubectl get pods -n test` |
| Helm release | `helm list -n test` |
| CI/CD pipeline | validate/build/deploy/smoke stages |
| Smoke logs | Успешная проверка API/frontend |
