# --- Builder stage ---
FROM python:3.11-slim AS builder

# Install build deps only at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim AS runtime

# curl is needed by the container healthcheck (both the HEALTHCHECK below and
# the compose-level one); libpq5 is the runtime half of libpq-dev.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy only the installed packages from builder
COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p /app/data/documents && chown -R appuser:appuser /app

EXPOSE 8000

# Healthcheck for orchestrators (k8s/compose)
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/health/ || exit 1

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
