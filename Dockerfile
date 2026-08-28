FROM python:3.13.15-alpine3.23

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/healthz \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200-399

RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 \
    /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

RUN addgroup -S app \
    && adduser -S -G app app

COPY requirements-prod.txt ./

RUN python -m pip install --upgrade "pip==26.2" \
    && python -m pip install --requirement requirements-prod.txt \
    && python -m pip check

COPY --chown=app:app backend ./backend
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/healthz', timeout=2)"

CMD ["python", "-m", "backend.config.bootstrap_runtime"]
