# Docker Setup for FastAPI Server

This guide explains how to build and run the FastAPI server using Docker.

## Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)

## Quick Start

### 1. Configure Environment

Copy the example environment file:

```bash
cd ml
cp .env.example .env
```

Edit `.env` and add your Supabase credentials:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
FASTAPI_ENV=production
LOG_LEVEL=info
```

### 2. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The API will be available at `http://localhost:8000`

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Technical indicators
curl "http://localhost:8000/api/v1/technical-indicators?symbol=AAPL&timeframe=d1"

# View API documentation
open http://localhost:8000/docs
```

## Docker Commands

### Build Image

```bash
# Build the Docker image
docker build -t swiftbolt-ml-api ./ml

# Build with specific tag
docker build -t swiftbolt-ml-api:latest ./ml
```

### Run Container

```bash
# Run container (detached mode)
docker run -d \
  --name swiftbolt-ml-api \
  -p 8000:8000 \
  --env-file .env \
  swiftbolt-ml-api

# Run with environment variables
docker run -d \
  --name swiftbolt-ml-api \
  -p 8000:8000 \
  -e SUPABASE_URL=https://your-project.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=your-key \
  swiftbolt-ml-api

# Run with volume mount (for development)
docker run -d \
  --name swiftbolt-ml-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/api:/app/api \
  -v $(pwd)/scripts:/app/scripts \
  swiftbolt-ml-api
```

### Container Management

```bash
# View logs
docker logs swiftbolt-ml-api
docker logs -f swiftbolt-ml-api  # Follow logs

# Stop container
docker stop swiftbolt-ml-api

# Start container
docker start swiftbolt-ml-api

# Remove container
docker rm swiftbolt-ml-api

# Execute command in running container
docker exec -it swiftbolt-ml-api bash

# View container stats
docker stats swiftbolt-ml-api
```

## Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Start with build
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild services
docker-compose build --no-cache

# View running services
docker-compose ps

# Execute command in service
docker-compose exec fastapi bash
```

## Development Mode

For development with hot-reload, modify `docker-compose.yml`:

```yaml
services:
  fastapi:
    # ... existing config ...
    command: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
    volumes:
      - ./api:/app/api
      - ./scripts:/app/scripts
      - ./src:/app/src
```

Then run:

```bash
docker-compose up
```

Changes to mounted files will automatically reload.

## Production Deployment

### Build for Production

```bash
# Build optimized image
docker build -t swiftbolt-ml-api:prod ./ml

# Tag for registry
docker tag swiftbolt-ml-api:prod your-registry/swiftbolt-ml-api:latest
```

### Push to Registry

```bash
# Docker Hub
docker push your-username/swiftbolt-ml-api:latest

# AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com
docker tag swiftbolt-ml-api:prod your-account.dkr.ecr.us-east-1.amazonaws.com/swiftbolt-ml-api:latest
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/swiftbolt-ml-api:latest

# Google Container Registry
docker tag swiftbolt-ml-api:prod gcr.io/your-project/swiftbolt-ml-api:latest
docker push gcr.io/your-project/swiftbolt-ml-api:latest
```

### Deploy to Cloud

#### AWS ECS

```bash
# Create ECS task definition
aws ecs register-task-definition \
  --family swiftbolt-ml-api \
  --container-definitions '[{
    "name": "fastapi",
    "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/swiftbolt-ml-api:latest",
    "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
    "environment": [
      {"name": "SUPABASE_URL", "value": "..."},
      {"name": "SUPABASE_SERVICE_ROLE_KEY", "value": "..."}
    ]
  }]'
```

#### Google Cloud Run

```bash
# Deploy to Cloud Run
gcloud run deploy swiftbolt-ml-api \
  --image gcr.io/your-project/swiftbolt-ml-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SUPABASE_URL=...,SUPABASE_SERVICE_ROLE_KEY=...
```

#### Azure Container Instances

```bash
az container create \
  --resource-group your-resource-group \
  --name swiftbolt-ml-api \
  --image your-registry/swiftbolt-ml-api:latest \
  --dns-name-label swiftbolt-ml-api \
  --ports 8000 \
  --environment-variables SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs swiftbolt-ml-api

# Check if port is already in use
lsof -i :8000

# Run interactively to debug
docker run -it --rm swiftbolt-ml-api bash
```

### Permission issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Or run with user flag
docker run -u $(id -u):$(id -g) ...
```

### Build fails

```bash
# Clean build
docker build --no-cache -t swiftbolt-ml-api ./ml

# Check Dockerfile syntax
docker build --dry-run ./ml
```

### Environment variables not loading

```bash
# Verify .env file exists
ls -la .env

# Check environment in container
docker exec swiftbolt-ml-api env

# Or use docker-compose config to verify
docker-compose config
```

## Health Checks

The Dockerfile includes a health check. Monitor it:

```bash
# Check container health
docker ps

# View health check status
docker inspect swiftbolt-ml-api | grep -A 10 Health
```

## Security Best Practices

1. **Use secrets management**: Don't hardcode credentials
2. **Non-root user**: Container runs as `appuser` (UID 1000)
3. **Minimal base image**: Uses `python:3.11-slim`
4. **Multi-stage build**: Reduces final image size
5. **.dockerignore**: Excludes unnecessary files

## Image Size Optimization

The multi-stage build reduces image size by:
- Only including runtime dependencies
- Removing build tools (gcc, g++, etc.) from final image
- Using slim Python base image

Check image size:

```bash
docker images swiftbolt-ml-api
```

## Next Steps

1. Set up CI/CD to automatically build and push images
2. Configure monitoring and logging
3. Set up auto-scaling based on load
4. Configure SSL/TLS termination
5. Set up backup and disaster recovery
