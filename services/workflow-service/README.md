# Workflow service

Saga/process manager. Управляет жизненным циклом заказа через Redis Streams, вызывает бизнес-сервисы и хранит workflow_runs.

Сервис входит в состав RetailOps-microservices-platform и запускается как отдельный FastAPI container.
