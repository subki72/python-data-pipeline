# Stage 1: Dependency Builder
FROM python:3.15-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Hardened Non-Root Runtime
FROM python:3.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --shell /sbin/nologin --create-home appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup main.py ./
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup migrations/ ./migrations/

RUN mkdir -p /app/data /app/credentials \
    && chown -R appuser:appgroup /app/data /app/credentials

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "main.py", "--health"]

CMD ["python", "main.py"]
