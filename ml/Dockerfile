# FastAPI Server Dockerfile
# Multi-stage build with Alpine for minimal image size

FROM python:3.10-alpine as builder

# Set working directory
WORKDIR /app

# Install build dependencies (Alpine package names)
RUN apk add --no-cache \
    gcc \
    g++ \
    cmake \
    make \
    musl-dev \
    linux-headers \
    postgresql-dev

# Copy requirements first for better caching
COPY requirements-docker.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-docker.txt

# Production stage
FROM python:3.10-alpine

# Set working directory
WORKDIR /app

# Install runtime dependencies only (Alpine package names)
RUN apk add --no-cache \
    postgresql-client \
    libgomp \
    libstdc++ \
    curl

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (using curl with explicit GET method)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f -X GET http://127.0.0.1:8000/health || exit 1

# Run FastAPI server without reload for stable production behavior
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
