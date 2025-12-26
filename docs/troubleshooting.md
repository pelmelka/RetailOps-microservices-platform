# Troubleshooting

## Docker Desktop is not running

Ошибка:

```text
failed to connect to dockerDesktopLinuxEngine
```

Действия:

```text
открыть Docker Desktop
дождаться статуса running
повторить docker compose up
```

## PostgreSQL connection refused

Проверить контейнер:

```bash
docker compose -f deploy/docker-compose/docker-compose.yml --env-file deploy/docker-compose/.env.example ps postgres
```

Проверить `DATABASE_URL`:

```bash
echo $DATABASE_URL
```

## Bootstrap failed

Повторить bootstrap с явно заданным `DATABASE_URL`:

```bash
export DATABASE_URL="postgresql+asyncpg://retailops:retailops_local_password@localhost:5432/retailops"
python scripts/db/bootstrap_local_db.py
```

## Helm lint failed

```bash
helm lint charts/retailops-microservices-platform
helm template retailops-test charts/retailops-microservices-platform -f charts/retailops-microservices-platform/values.test.yaml --namespace test
```

Проверить YAML indentation, required values и template functions.

## ImagePullBackOff

Проверить registry secret:

```bash
kubectl get secret gitlab-registry -n test
kubectl describe pod <pod> -n test
```

Пересоздать secret:

```bash
sh scripts/gitlab-ci/ensure_registry_secret.sh test
```

## Pod is not ready

```bash
kubectl describe pod <pod> -n test
kubectl logs <pod> -n test
```

Проверить readiness endpoint:

```bash
kubectl port-forward svc/api-gateway 8000:8000 -n test
curl http://localhost:8000/ready
```

## Ingress does not open

Проверить:

```bash
kubectl get ingress -n test
kubectl describe ingress -n test
kubectl get svc -A | grep ingress
```

Проверить host в values:

```yaml
ingress:
  host: test.retailops.internal
```

## Smoke failed

Посмотреть smoke log artifact или выполнить вручную:

```bash
sh scripts/gitlab-ci/smoke_k8s.sh test
```

Проверить сервисы:

```bash
kubectl get pods -n test
kubectl get svc -n test
kubectl logs deployment/api-gateway -n test
kubectl logs deployment/frontend-dashboard -n test
```
