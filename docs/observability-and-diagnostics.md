# Observability and diagnostics

## Health and readiness

Backend-сервисы предоставляют:

```text
GET /health
GET /ready
```

Kubernetes probes используют эти endpoint-ы для проверки контейнеров.

## Correlation ID

HTTP-запросы поддерживают `X-Correlation-ID`.

Если заголовок передан клиентом, сервис возвращает тот же идентификатор. Если заголовок отсутствует, middleware генерирует новый correlation ID.

## Structured logs

Общий logging helper формирует JSON-логи с полями:

```text
timestamp
level
logger
message
service
correlation_id
method
path
status_code
user_id
order_id
document_id
payment_id
notification_id
step
status
```

## Redis Streams diagnostics

Просмотр команд:

```bash
kubectl exec -n test statefulset/redis -- redis-cli XRANGE project.workflow.commands - +
```

Просмотр событий:

```bash
kubectl exec -n test statefulset/redis -- redis-cli XRANGE project.workflow.events - +
```

Просмотр dead letter stream:

```bash
kubectl exec -n test statefulset/redis -- redis-cli XRANGE project.workflow.dead_letter - +
```

## Kubernetes diagnostics

```bash
kubectl get pods -n test
kubectl describe pod <pod> -n test
kubectl logs deployment/api-gateway -n test
kubectl logs deployment/workflow-service -n test
kubectl rollout status deployment/api-gateway -n test --timeout=5m
```

## Database diagnostics

Bootstrap Job:

```bash
kubectl get jobs -n test
kubectl logs job/<bootstrap-job-name> -n test
```

PostgreSQL pod:

```bash
kubectl get statefulset postgres -n test
kubectl logs statefulset/postgres -n test
```
