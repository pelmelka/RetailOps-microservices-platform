# SPECIFICATION.md

# RetailOps-microservices-platform — техническая спецификация

## Назначение

RetailOps-microservices-platform — контейнеризованная микросервисная система с Kubernetes deployment model и CI/CD-доставкой через Helm.

Проект состоит из прикладных backend-сервисов, frontend-dashboard, локального Docker Compose-профиля, Helm chart, values-файлов для `test` и `prod`, pipeline-скриптов и smoke-проверок.

## Компоненты

| Компонент | Назначение |
|---|---|
| frontend-dashboard | Пользовательский dashboard на React + TypeScript |
| api-gateway | Внешняя HTTP-граница, auth boundary, ownership и idempotency |
| workflow-service | Saga/process manager для заказа и оплаты |
| auth-service | Регистрация, вход, password_hash, JWT, current user context |
| catalog-service | Каталог товаров и цены в копейках |
| order-service | Заказы, снимок цены, статусы и история статусов |
| payment-service | Локальная обработка платежей с контролируемыми сценариями |
| document-service | Генерация PDF-счёта и PDF-чека, хранение метаданных |
| notification-service | Email-уведомления через SMTP-профиль |
| PostgreSQL | Основное состояние приложения |
| Redis | Redis Streams command/event transport |
| Mailpit | SMTP sink и UI для просмотра писем |

## Public API через api-gateway

Public endpoints:

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/catalog/items
GET  /api/catalog/items/{item_id}
```

Protected endpoints:

```text
GET  /api/auth/me
GET  /api/orders
GET  /api/orders/{order_id}
GET  /api/orders/{order_id}/history
GET  /api/orders/{order_id}/workflow
GET  /api/orders/{order_id}/documents/{document_id}/download
GET  /api/workflows/{workflow_id}
POST /api/orders
POST /api/orders/{order_id}/payments
```

Service endpoints for internal communication сохраняются за соответствующими сервисами и не используются frontend-dashboard напрямую.

## Workflow model

Создание заказа:

```text
POST /api/orders
  -> api-gateway validates JWT and Idempotency-Key
  -> workflow-service creates workflow_run
  -> Redis command order.create
  -> order-service creates order
  -> document-service generates invoice
  -> workflow status awaiting_payment
```

Оплата:

```text
POST /api/orders/{order_id}/payments
  -> api-gateway checks owner and Idempotency-Key
  -> workflow-service accepts payment request
  -> Redis command payment.process
  -> payment-service processes scenario
  -> document-service generates receipt on success
  -> notification-service sends email
  -> workflow status completed or failed
```

## Redis Streams

Streams:

```text
project.workflow.commands
project.workflow.events
project.workflow.dead_letter
```

Основные command/event types:

| Тип | Назначение |
|---|---|
| order.create | Создание заказа |
| document.generate_invoice | Генерация счёта |
| workflow.awaiting_payment | Переход workflow в ожидание оплаты |
| payment.process | Обработка платежа |
| payment.completed | Успешная оплата |
| payment.failed | Ошибка оплаты |
| document.generate_receipt | Генерация чека |
| notification.send | Отправка уведомления |
| workflow.completed | Завершение workflow |
| workflow.failed | Ошибка workflow |

Durable state хранится в PostgreSQL. Redis Streams используется как транспорт команд и событий.

## PostgreSQL schema

Схема управляется Alembic migrations.

Основные таблицы:

```text
auth_users
catalog_items
orders
order_status_history
payments
document_metadata
notifications
gateway_idempotency_keys
workflow_runs
processed_stream_messages
```

## Money model

Денежная модель использует RUB и integer kopecks:

```text
price_kopecks
unit_price_kopecks
total_kopecks
amount_kopecks
```

## Provider boundaries

| Boundary | Реализация |
|---|---|
| Payment | LocalPaymentProvider с controlled scenarios |
| Document | ReportLab PDF generator и storage volume |
| Notification | SMTP provider через Mailpit |

Payment scenarios:

```text
success
insufficient_funds
provider_unavailable
suspected_fraud
```

## Kubernetes deployment model

Helm chart: `charts/retailops-microservices-platform`.

Chart включает:

```text
Deployment: api-gateway, backend services, workflow-service, frontend-dashboard, mailpit
StatefulSet: postgres, redis
Service: все runtime-компоненты
Ingress: HTTP entrypoint
ConfigMap: service configuration
Secret: application and database secrets
PVC: document storage
Job: bootstrap database
```

Окружения:

```text
namespace test  -> values.test.yaml
namespace prod  -> values.prod.yaml
```

Доставка выполняется командой `helm upgrade --install`.

## CI/CD pipeline

Stages:

```text
validate
build
deploy_test
smoke_test
deploy_prod
smoke_prod
```

Validation:

```text
changed artifacts detection
python compile
pytest
frontend build
helm lint
helm template
shell syntax check
```

Build:

```text
changed backend images
changed frontend image
image tag by commit SHA
push to registry
```

Deploy:

```text
helm upgrade --install to test
smoke test
manual promote to prod
helm upgrade --install to prod
smoke prod
```

## Configuration

Key environment variables:

```text
DATABASE_URL
REDIS_URL
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES
DOCUMENT_STORAGE_DIR
PAYMENT_PROVIDER
NOTIFICATION_PROVIDER
SMTP_HOST
SMTP_PORT
SMTP_FROM
AUTH_SERVICE_URL
CATALOG_SERVICE_URL
ORDER_SERVICE_URL
DOCUMENT_SERVICE_URL
PAYMENT_SERVICE_URL
NOTIFICATION_SERVICE_URL
WORKFLOW_SERVICE_URL
UPSTREAM_TIMEOUT_SECONDS
GATEWAY_CORS_ALLOWED_ORIGINS
```

CI/CD variables:

```text
KUBE_CONFIG_B64
TEST_INGRESS_HOST
PROD_INGRESS_HOST
MWP_POSTGRES_PASSWORD
MWP_JWT_SECRET_KEY
K8S_REGISTRY_USER
K8S_REGISTRY_PASSWORD
```

## Readiness and health

Backend services expose:

```text
GET /health
GET /ready
```

Kubernetes probes use service health/readiness endpoints.

## Frontend

Frontend-dashboard:

```text
React
TypeScript
Vite
nginx static serving in Kubernetes image
API access through api-gateway only
```

Dashboard displays:

```text
login/register
catalog
order creation
workflow status
invoice/receipt download
payment scenario selector
order history
debug trace panel
```
