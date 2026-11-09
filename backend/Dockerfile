# ---------------------------------------------------------------------------
# RentEase - Application tier (Flask REST API served by gunicorn)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer is cached between code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code (.dockerignore keeps .env, .venv, local DBs and uploads out).
COPY . .

# Run as an unprivileged user (least privilege).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app/uploads
USER appuser

EXPOSE 5000

# Container-level health check (the load balancer uses /api/health).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health/live', timeout=4)" || exit 1

# Extra gunicorn options can be passed with the GUNICORN_CMD_ARGS env variable.
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "--timeout", "60", "wsgi:app"]
