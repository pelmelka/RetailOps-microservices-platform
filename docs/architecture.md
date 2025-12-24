# Архитектура

## Общая схема

```text
Browser
  -> frontend-dashboard
  -> api-gateway
  -> auth-service
  -> catalog-service
  -> workflow-service
        -> Redis Streams
        -> order-service
        -> document-service
        -> payment-service
        -> notification-service
  -> PostgreSQL
  -> Redis
  -> Mailpit
```

`api-gateway` является внешней HTTP-границей приложения. Frontend вызывает только `/api/*` маршруты gateway.

`workflow-service` управляет процессом заказа как saga/process manager. Он не заменяет бизнес-сервисы, а координирует их через команды, события и HTTP-вызовы.

## Границы сервисов

| Сервис | Владение |
|---|---|
| auth-service | Пользователи, password_hash, JWT, current user context |
| catalog-service | Каталог и цены |
| order-service | Заказы, статусы, история, price snapshot |
| payment-service | Платёжные записи и payment scenarios |
| document-service | PDF-файлы, metadata, download |
| notification-service | Email-уведомления и delivery metadata |
| workflow-service | workflow_runs, process progression, Redis Streams processing |
| api-gateway | Auth boundary, ownership, idempotency, external API |

## Поток заказа

```text
POST /api/orders
  -> validate auth
  -> check Idempotency-Key
  -> create workflow_run
  -> emit order.create
  -> create order
  -> generate invoice
  -> awaiting_payment
```

Оплата запускается отдельным действием пользователя:

```text
POST /api/orders/{order_id}/payments
  -> ownership check
  -> idempotency check
  -> payment.process
  -> payment result
  -> receipt + notification
```

## Хранилища

PostgreSQL хранит durable state: пользователей, каталог, заказы, документы, платежи, уведомления, workflow и idempotency keys.

Redis Streams используется как transport layer для команд и событий workflow.

PDF-файлы хранятся в document storage volume, метаданные — в PostgreSQL.
