# 🐳 SwiftBolt Backend with Docker

This guide shows how to run the SwiftBolt FastAPI backend using Docker instead of running it manually with `uvicorn`.

## ✅ What's Included

- **Dockerfile**: Multi-stage build for optimized image (~1GB)
- **docker-compose.yml**: Easy container management
- **.dockerignore**: Excludes unnecessary files
- **requirements-docker.txt**: Dependencies optimized for Docker (TensorFlow excluded for ARM64 compatibility)

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed and running
- Located in: `/Users/ericpeterson/SwiftBolt_ML/`

### Option 1: Run with Docker Compose (Recommended)

```bash
# Start the backend in Docker
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop the backend
docker-compose down

# Restart the backend
docker-compose restart backend
```

### Option 2: Manual Docker Commands

```bash
# Build the image
docker build -f ml/Dockerfile -t swiftbolt-backend ml/

# Run the container
docker run -d \
  --name swiftbolt-backend \
  -p 8000:8000 \
  -v $(pwd)/ml:/app \
  swiftbolt-backend

# View logs
docker logs -f swiftbolt-backend

# Stop the container
docker stop swiftbolt-backend

# Remove the container
docker rm swiftbolt-backend
```

## 📝 How It Works

### Docker Compose File

The `docker-compose.yml` includes:

```yaml
services:
  backend:
    build:
      context: ./ml
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./ml:/app  # Live code reloading
    restart: unless-stopped
    healthcheck:
      test: wget --spider http://localhost:8000/health
      interval: 30s
```

**Key Features:**
- ✅ **Live code reloading**: Changes to Python files reload automatically
- ✅ **Health checks**: Docker monitors if the API is healthy
- ✅ **Auto-restart**: Container restarts if it crashes
- ✅ **Port mapping**: Exposes port 8000

### Dockerfile

The Dockerfile uses a multi-stage build:

```dockerfile
# Stage 1: Builder
- Installs build dependencies
- Installs Python packages
- Total size kept small

# Stage 2: Runtime
- Lean production image
- Only runtime dependencies
- Non-root user (appuser)
- Health check enabled
```

## 🔍 Verify It's Working

```bash
# Check if container is running
docker ps | grep swiftbolt

# Test the health endpoint
curl http://localhost:8000/health

# Test the real-time charts API
curl http://localhost:8000/api/v1/health/realtime-charts

# Check active WebSocket connections
curl http://localhost:8000/api/v1/health/realtime-charts | jq '.active_connections'
```

## 📊 Status Commands

```bash
# View running containers
docker-compose ps

# View detailed logs
docker-compose logs -f backend --tail=100

# View Docker stats (CPU, memory)
docker stats swiftbolt-ml-backend

# Inspect the image
docker inspect swiftbolt-ml-backend:latest

# Remove unused images
docker image prune
```

## 🛠️ Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker-compose logs backend

# Rebuild from scratch
docker-compose build --no-cache

# Start with more verbose output
docker-compose up backend  # (remove -d flag)
```

### Port 8000 already in use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port in docker-compose.yml
ports:
  - "8001:8000"  # Access at localhost:8001
```

### Live reloading not working

```bash
# Check volume mounts
docker inspect swiftbolt-ml-backend | grep Mounts

# Ensure the mount path is correct
docker-compose exec backend ls -la /app
```

### Container crashes on startup

```bash
# Check if it's a dependency issue
docker-compose build --no-cache

# Check if requirements-docker.txt is correct
docker-compose exec backend pip list
```

## 📈 Performance

### Image Size
- Builder stage: ~2.5GB (discarded)
- Final image: ~1GB
- Runtime: ~150-200MB (depends on loaded models)

### Startup Time
- First run: ~30 seconds (includes dependencies)
- Subsequent runs: ~5 seconds

### CPU/Memory Usage
- Idle: ~30-50MB
- During requests: ~100-200MB
- Peak (ML inference): ~500MB-1GB

## 🔄 Updating Dependencies

If you modify `requirements.txt`:

```bash
# Create requirements-docker.txt without tensorflow
cp requirements.txt requirements-docker.txt
# Edit to remove tensorflow line

# Rebuild the image
docker-compose build --no-cache

# Restart the container
docker-compose restart backend
```

## 📚 Common Workflows

### Development (Live Reloading)

```bash
# Start the backend with live code reloading
docker-compose up -d

# Make changes to Python files
# Changes auto-reload (no restart needed!)

# View logs
docker-compose logs -f backend

# Stop when done
docker-compose down
```

### Testing

```bash
# Start the backend
docker-compose up -d

# Run tests against localhost:8000
pytest tests/

# Stop the backend
docker-compose down
```

### Debugging

```bash
# Start without detaching (see output in real-time)
docker-compose up backend

# In another terminal, exec into the container
docker-compose exec backend /bin/bash

# Run commands inside
python -c "import api.main; print(api.main.app.routes)"
```

## 🌐 From macOS App

The macOS app automatically detects and connects to the Docker container:

1. ✅ Docker container running on `localhost:8000`
2. ✅ SwiftBolt app loads real-time forecast charts
3. ✅ WebSocket connection established automatically
4. ✅ No configuration needed!

## 📋 Checklist

- [ ] Docker Desktop is installed and running
- [ ] Located in `/Users/ericpeterson/SwiftBolt_ML/`
- [ ] Run `docker-compose up -d` to start
- [ ] Verify with `curl http://localhost:8000/health`
- [ ] Check logs with `docker-compose logs -f backend`
- [ ] Test from macOS app by opening a chart

## 🎯 Next Steps

```bash
# 1. Start the Docker backend
docker-compose up -d

# 2. Run the macOS app in Xcode (⌘ + R)

# 3. Open a chart view

# 4. You should see:
#    - Chart loads quickly
#    - Forecast markers appear
#    - WebSocket shows "Live"

# 5. When done, stop the container
docker-compose down
```

## 📞 Support

If you encounter issues:

1. Check logs: `docker-compose logs backend`
2. Check health: `curl http://localhost:8000/health`
3. Verify port: `lsof -i :8000`
4. Rebuild: `docker-compose build --no-cache`

## ✨ Benefits

✅ No need to reload terminal
✅ Auto-restart on crash
✅ Live code reloading
✅ Clean separation of concerns
✅ Easy to scale
✅ Production-ready setup
✅ Health checks built-in
✅ Container isolation

---

**Ready to use Docker?**

```bash
docker-compose up -d
```

🚀 Your backend is now running in Docker!
