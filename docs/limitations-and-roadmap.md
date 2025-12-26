# Границы текущей версии и roadmap

## Границы текущей версии

Текущая версия включает:

```text
Docker Compose local runtime
Kubernetes Helm chart
CI/CD pipeline
test/prod namespaces
Redis Streams workflow
PostgreSQL persistence
frontend-dashboard
PDF documents
SMTP profile through Mailpit
smoke checks
```

Текущая версия не включает:

```text
external managed PostgreSQL profile
external managed Redis profile
TLS certificate automation
Prometheus/Grafana stack
centralized log storage
horizontal document storage with RWX/object storage
real payment provider integration
real email provider integration
multi-cluster deployment
```

## Roadmap

### 1. Observability profile

```text
/metrics endpoints
Prometheus scrape config
Grafana dashboard
workflow-level metrics
service latency/error panels
```

### 2. TLS and ingress hardening

```text
TLS values profile
cert-manager issuer values
HTTPS ingress
security headers
```

### 3. External stateful services profile

```text
external PostgreSQL URL
external Redis URL
managed secret strategy
backup/restore runbook
```

### 4. Storage profile

```text
RWX storage class or object storage boundary
separate document storage values
retention policy
```

### 5. Extended deployment checks

```text
full workflow smoke in Kubernetes
payment failure smoke
document download smoke
notification smoke
rollback verification
```
