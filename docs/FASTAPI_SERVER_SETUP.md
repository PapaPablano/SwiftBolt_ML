# FastAPI Server Setup Guide

## Overview

This guide explains how to set up a FastAPI server to expose your ML Python scripts as REST APIs. This is the recommended production approach for integrating ML functionality with Supabase Edge Functions.

## Why FastAPI?

- **Production-Ready**: Better error handling, logging, and monitoring
- **Scalable**: Can handle concurrent requests efficiently
- **Type-Safe**: Uses Pydantic for request/response validation
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Deployment Options**: Easy to deploy on various platforms (Railway, Render, AWS, etc.)

## Architecture

```
┌─────────────────┐
│  SwiftUI App    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Supabase Edge    │
│ Functions        │
│ (TypeScript)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  FastAPI Server  │
│  (Python)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ML Scripts     │
│  (Python)       │
└─────────────────┘
```

## Step 1: Install FastAPI Dependencies

Add FastAPI and Uvicorn to your requirements:

```bash
cd ml
pip install fastapi>=0.104.0 uvicorn[standard]>=0.24.0
```

Or add to `ml/requirements.txt`:

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
```

## Step 2: Create FastAPI Server Structure

Create the following directory structure:

```
ml/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── technical_indicators.py
│   │   ├── backtest.py
│   │   ├── walk_forward.py
│   │   ├── portfolio.py
│   │   └── stress_test.py
│   └── models/
│       ├── __init__.py
│       ├── technical_indicators.py
│       ├── backtest.py
│       ├── walk_forward.py
│       ├── portfolio.py
│       └── stress_test.py
```

## Step 3: Create Pydantic Models

Create request/response models in `ml/api/models/` for type safety and validation.

## Step 4: Create API Routers

Create router files in `ml/api/routers/` that wrap your existing CLI scripts.

## Step 5: Create Main FastAPI App

Create `ml/api/main.py` that includes all routers and sets up CORS.

## Step 6: Update Edge Functions

Modify your Supabase Edge Functions to call the FastAPI server instead of executing Python scripts directly.

## Step 7: Configure Environment Variables

Set up environment variables for:
- FastAPI server URL
- Supabase credentials (for ML scripts)
- API keys/secrets

## Step 8: Deploy FastAPI Server

Choose a deployment platform and deploy your FastAPI server.

## Detailed Implementation

See the sample FastAPI server code in `ml/api/` directory (created by this guide).

## Testing

### Local Testing

```bash
# Start FastAPI server
cd ml
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Test endpoint
curl http://localhost:8000/api/v1/technical-indicators?symbol=AAPL&timeframe=d1
```

### Test from Edge Function

Update Edge Function to point to local server:

```typescript
const FASTAPI_URL = Deno.env.get("FASTAPI_URL") || "http://localhost:8000";
```

## Deployment Options

### Option 1: Railway (Recommended for Simplicity)

1. Create `railway.json`:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd ml && uvicorn api.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

2. Connect GitHub repo to Railway
3. Set environment variables in Railway dashboard
4. Deploy

### Option 2: Render

1. Create `render.yaml`:
```yaml
services:
  - type: web
    name: swiftbolt-ml-api
    env: python
    buildCommand: cd ml && pip install -r requirements.txt
    startCommand: cd ml && uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
```

2. Connect repo to Render
3. Set environment variables
4. Deploy

### Option 3: AWS Lambda (Serverless)

Use Mangum to wrap FastAPI for Lambda:

```bash
pip install mangum
```

Update `ml/api/main.py`:
```python
from mangum import Mangum
handler = Mangum(app)
```

### Option 4: Docker (Recommended)

Docker setup is already configured! See `ml/DOCKER_SETUP.md` for detailed instructions.

**Quick start:**

```bash
cd ml

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Test API
curl http://localhost:8000/health
```

**Docker features:**
- Multi-stage build for optimized image size
- Health checks included
- Non-root user for security
- Development mode with hot-reload support
- Production-ready configuration

See `ml/DOCKER_SETUP.md` for:
- Detailed Docker commands
- Production deployment options
- Troubleshooting guide
- Security best practices

## Environment Variables

Set these in your deployment platform:

```bash
# Supabase (for ML scripts)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# FastAPI
FASTAPI_ENV=production
LOG_LEVEL=info

# Optional: API Keys
API_KEY=your-secret-api-key  # For securing endpoints
```

## Security Considerations

1. **API Authentication**: Add API key authentication to FastAPI endpoints
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **CORS**: Configure CORS to only allow requests from your Supabase Edge Functions
4. **Input Validation**: Use Pydantic models to validate all inputs
5. **Error Handling**: Don't expose internal errors to clients

## Monitoring

1. **Health Check Endpoint**: Add `/health` endpoint
2. **Logging**: Use structured logging (JSON format)
3. **Metrics**: Consider adding Prometheus metrics
4. **Error Tracking**: Integrate Sentry or similar

## Next Steps

1. Review the sample FastAPI server code in `ml/api/`
2. Customize endpoints as needed
3. Add authentication/rate limiting
4. Deploy to your chosen platform
5. Update Edge Functions to use FastAPI URLs
6. Test end-to-end from SwiftUI app

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure `ml/src` is in Python path
2. **Database Connection**: Verify Supabase credentials
3. **Timeout Errors**: Increase timeout for long-running operations
4. **Memory Issues**: Consider adding request timeouts and memory limits

### Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check FastAPI docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
