# ---------- Student Management System image ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQLITE_PATH=/data/students.db \
    PORT=5000

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user and give it a writable data dir
RUN useradd --create-home --uid 10001 appuser && mkdir /data && chown appuser /data
USER appuser

# Injected by CI (docker build --build-arg APP_VERSION=<git sha>)
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health').status==200 else 1)"

# 1 worker + threads keeps the in-process /metrics counters accurate; scale with replicas.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app.app:app"]
