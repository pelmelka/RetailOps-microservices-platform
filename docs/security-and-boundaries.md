# Security and boundaries

## Auth boundary

`auth-service` отвечает за:

```text
registration
password_hash
password verification
JWT issue
current user context
```

`api-gateway` не принимает `user_id` от клиента для protected workflow-команд. Текущий пользователь определяется через auth boundary.

## Gateway boundary

`api-gateway` выполняет:

```text
public/protected route split
current user resolution
ownership checks
idempotency checks
correlation-id propagation
upstream timeout handling
error mapping
CORS boundary
```

## Ownership

Protected resources проверяются по owner relationship:

```text
order.user_id == current_user.user_id
workflow.user_id == current_user.user_id
document belongs to order
```

Для чужих ресурсов возвращается not found response.

## Idempotency

Protected mutation endpoints требуют `Idempotency-Key`.

Gateway сохраняет результат mutation в PostgreSQL-backed idempotency layer.

## Secrets

Kubernetes secrets передаются через Helm values и CI/CD variables:

```text
MWP_JWT_SECRET_KEY
MWP_POSTGRES_PASSWORD
```

Registry secret создаётся скриптом `ensure_registry_secret.sh`.

## Network boundaries

Frontend-dashboard обращается только к api-gateway.

Внутренние сервисы доступны по Kubernetes Service DNS внутри namespace.

## CORS

CORS origins задаются через values:

```yaml
apiGateway:
  corsAllowedOrigins: http://test.retailops.internal
```
