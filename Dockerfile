# OCI Robot Cloud — API Services Container
# Lightweight Python image for all FastAPI services (non-GPU).
# GPU-dependent services (GR00T inference, training) use the OCI bare-metal A100 directly.

FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    numpy \
    pydantic \
    && pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

COPY src/ ./src/
COPY docs/ ./docs/

# Default health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8004}/health || exit 1

# Non-root user
RUN useradd -m -u 1000 ocirc
USER ocirc

CMD ["python", "src/api/analytics_dashboard.py"]
