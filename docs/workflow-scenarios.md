# Workflow scenarios

## Happy path

```text
register/login
  -> catalog
  -> create order
  -> invoice generated
  -> awaiting_payment
  -> payment success
  -> receipt generated
  -> notification sent
  -> workflow completed
```

## Payment failure scenarios

Payment service поддерживает контролируемые сценарии:

```text
insufficient_funds
provider_unavailable
suspected_fraud
```

При ошибке оплаты workflow фиксирует failure code и отображает состояние в API/dashboard.

## Documents

Document service генерирует:

```text
invoice PDF
receipt PDF
```

Файл сохраняется в document storage volume. Метаданные сохраняются в PostgreSQL:

```text
document_id
order_id
document_type
content_type
size_bytes
checksum_sha256
storage_path
created_at
```

## Notifications

Notification service отправляет email через SMTP-профиль Mailpit.

В Kubernetes Mailpit запускается как отдельный deployment/service.

## Smoke scripts

Локальный smoke:

```bash
python scripts/smoke/check_async_workflow.py
```

Kubernetes smoke:

```bash
sh scripts/gitlab-ci/smoke_k8s.sh test
sh scripts/gitlab-ci/smoke_k8s.sh prod
```
