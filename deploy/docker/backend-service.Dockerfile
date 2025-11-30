FROM python:3.13-slim

ARG SERVICE_PATH
ARG SERVICE_MODULE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SERVICE_MODULE=${SERVICE_MODULE}

WORKDIR /app

RUN test -n "${SERVICE_PATH}" && test -n "${SERVICE_MODULE}"

RUN python -m pip install --upgrade pip

COPY packages/shared /build/packages/shared
RUN python -m pip install /build/packages/shared

COPY ${SERVICE_PATH} /build/service
RUN python -m pip install /build/service \
    && python -m pip install "uvicorn>=0.30,<1.0"

COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY scripts/db /app/scripts/db

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app --no-create-home app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn ${SERVICE_MODULE} --host 0.0.0.0 --port 8000"]
