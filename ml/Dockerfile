# FastAPI Server Dockerfile
# Multi-stage build with Ubuntu 26.04

FROM ubuntu:26.04 AS builder

# Set working directory
WORKDIR /app

# Install Python and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    gcc \
    g++ \
    cmake \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-docker.txt .

# Use a venv to satisfy PEP 668 (externally-managed-environment) on Ubuntu 26.04
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/venv/bin/pip install --no-cache-dir -r requirements-docker.txt

# Production stage
FROM ubuntu:26.04

# Set working directory
WORKDIR /app

# Install Python and runtime dependencies only (no pip - we use the venv)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    libpq5 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder (includes all Python deps and uvicorn)
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
# Copy application code
COPY . .

# Create non-root user for security (UID 1001; 1000 is used by default in ubuntu image)
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (using curl with explicit GET method)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f -X GET http://127.0.0.1:8000/health || exit 1

# Run FastAPI server without reload for stable production behavior (use venv path explicitly)
CMD ["/app/venv/bin/uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
