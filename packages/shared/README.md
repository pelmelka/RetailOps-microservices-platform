# Shared backend package

Общий Python-пакет для backend-сервисов RetailOps-microservices-platform.

Содержит:

- фабрику FastAPI-приложения;
- `/health` и `/ready` endpoint-ы;
- middleware для `X-Correlation-ID`;
- JSON-логирование;
- helpers для конфигурации, PostgreSQL и Redis Streams.
