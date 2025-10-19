# API Gateway

Внешняя HTTP-граница приложения. Обрабатывает публичные и защищённые маршруты, проверяет пользователя через auth-service, выполняет ownership checks, idempotency и маршрутизацию команд workflow-service.

Сервис входит в состав RetailOps-microservices-platform и запускается как отдельный FastAPI container.
