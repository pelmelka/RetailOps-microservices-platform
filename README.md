# RetailOps-microservices-platform

RetailOps-microservices-platform — проект контейнеризованной микросервисной системы с доставкой в Kubernetes через Helm и CI/CD pipeline.

Прикладной сценарий: пользователь регистрируется, получает каталог товаров, создаёт заказ, получает PDF-счёт, выполняет оплату, получает PDF-чек и email-уведомление.

## Что входит в проект

| Область | Реализация |
|---|---|
| Контейнеризация | Dockerfile для backend-сервисов и frontend-dashboard |
| Локальный запуск | Docker Compose с PostgreSQL, Redis, Mailpit и сервисами приложения |
| Kubernetes | Helm chart с Deployment, Service, StatefulSet, Job, Secret, ConfigMap, PVC и Ingress |
| Окружения | Отдельные values-файлы и namespaces `test` и `prod` |
| CI/CD | Проверки, сборка изменённых образов, публикация в registry, Helm deploy, smoke-проверки |
| Backend | FastAPI-сервисы, PostgreSQL, Redis Streams, JWT, idempotency, ownership checks |
| Frontend | React + TypeScript + Vite dashboard |
| Документы | PDF-счёт и PDF-чек через document-service |
| Уведомления | SMTP-профиль через Mailpit |

## Структура репозитория

```text
.
├── .gitlab-ci.yml
├── README.md
├── SPECIFICATION.md
├── charts/
│   └── retailops-microservices-platform/
├── deploy/
│   ├── docker/
│   ├── docker-compose/
│   └── kubernetes/
├── docs/
├── migrations/
├── packages/
│   └── shared/
├── scripts/
│   ├── db/
│   ├── gitlab-ci/
│   └── smoke/
└── services/
    ├── api-gateway/
    ├── auth-service/
    ├── catalog-service/
    ├── order-service/
    ├── payment-service/
    ├── document-service/
    ├── notification-service/
    ├── workflow-service/
    └── frontend-dashboard/
```

## Контур развёртывания

Основной путь доставки приложения:

```text
commit / merge
  -> detect changed artifacts
  -> Python compile / pytest / frontend build / helm lint
  -> build changed Docker images
  -> push images to registry
  -> deploy to namespace test
  -> smoke test
  -> manual promote to namespace prod
  -> smoke prod
```

Доставка выполняется через Helm:

```bash
helm upgrade --install retailops charts/retailops-microservices-platform \
  --namespace test \
  --create-namespace \
  -f charts/retailops-microservices-platform/values.test.yaml \
  --set-string global.imageRegistry="$IMAGE_REGISTRY" \
  --set-string images.apiGateway.tag="$IMAGE_TAG" \
  --atomic \
  --wait \
  --timeout 10m
```

Для `prod` используется тот же chart, namespace `prod` и `values.prod.yaml`.

## Kubernetes profile

Helm chart описывает:

- `api-gateway` как внешнюю HTTP-границу приложения;
- backend-сервисы как отдельные Deployment и Service;
- `workflow-service` как отдельный process manager;
- `frontend-dashboard` как nginx-served static frontend;
- PostgreSQL и Redis как StatefulSet;
- Mailpit как SMTP/UI service;
- PVC для PDF-документов;
- bootstrap Job для применения миграций и seed-данных;
- Ingress для входа в приложение.

Окружения разделяются values-файлами:

```text
charts/retailops-microservices-platform/values.test.yaml
charts/retailops-microservices-platform/values.prod.yaml
deploy/kubernetes/environments/test.values.example.yaml
deploy/kubernetes/environments/prod.values.example.yaml
```

## CI/CD

Pipeline состоит из стадий:

```text
validate -> build -> deploy_test -> smoke_test -> deploy_prod -> smoke_prod
```

Проверки в `validate`:

- определение изменённых сервисов и deploy-артефактов;
- `python -m compileall`;
- `pytest`;
- `npm run build` для frontend-dashboard;
- `helm lint` и `helm template` для test/prod;
- синтаксическая проверка shell-скриптов.

Сборка образов выполняется только для сервисов, затронутых изменениями. Для каждого изменённого сервиса формируется отдельный Docker image tag на основе commit SHA.

## Локальный запуск

Локальный профиль нужен для проверки приложения без Kubernetes:

```bash
docker compose -f deploy/docker-compose/docker-compose.yml --env-file deploy/docker-compose/.env.example up --build -d
```

После старта применяются миграции и seed-данные:

```bash
export DATABASE_URL="postgresql+asyncpg://retailops:retailops_local_password@localhost:5432/retailops"
python scripts/db/bootstrap_local_db.py
```

Smoke-проверка async workflow:

```bash
python scripts/smoke/check_async_workflow.py
```

Основные локальные адреса:

| Компонент | Адрес |
|---|---|
| frontend-dashboard | http://localhost:3000 |
| api-gateway | http://localhost:8000 |
| Mailpit UI | http://localhost:8025 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## Пользовательский сценарий

```text
frontend-dashboard
  -> api-gateway
  -> auth-service / catalog-service / workflow-service
  -> Redis Streams
  -> order-service
  -> document-service
  -> payment-service
  -> notification-service
  -> PostgreSQL
```

Основной поток:

1. Регистрация или вход пользователя.
2. Получение каталога товаров.
3. Создание заказа.
4. Генерация PDF-счёта.
5. Ожидание оплаты.
6. Обработка платежа.
7. Генерация PDF-чека.
8. Отправка email-уведомления.
9. Отображение истории заказа и статуса workflow.

## Документация

| Файл | Содержание |
|---|---|
| `SPECIFICATION.md` | Полная техническая спецификация проекта |
| `docs/architecture.md` | Архитектура приложения и границы сервисов |
| `docs/runtime-and-deployment.md` | Локальный runtime и общий порядок развёртывания |
| `docs/kubernetes-and-helm.md` | Helm chart, namespaces, values и Kubernetes resources |
| `docs/ci-cd.md` | Pipeline, сборка образов, deploy и smoke-проверки |
| `docs/workflow-scenarios.md` | Основные workflow-сценарии |
| `docs/security-and-boundaries.md` | Auth, JWT, ownership, idempotency и secrets |
| `docs/observability-and-diagnostics.md` | Health/readiness, логи, Redis Streams и диагностика |
| `docs/demo-guide.md` | Сценарий демонстрации проекта |
| `docs/troubleshooting.md` | Частые проблемы запуска и деплоя |
| `docs/limitations-and-roadmap.md` | Границы текущей версии и дальнейшие направления |
| `docs/visual-assets-map.md` | Карта схем и скриншотов для README/портфолио |

## Быстрые проверки

```bash
python -m compileall packages/shared services scripts migrations
python -m pytest --basetemp=.pytest-tmp-run
cd services/frontend-dashboard && npm run build
helm lint charts/retailops-microservices-platform
helm template retailops-test charts/retailops-microservices-platform -f charts/retailops-microservices-platform/values.test.yaml --namespace test
```
