# FastAPI Server for SwiftBolt ML

REST API server exposing ML Python scripts as HTTP endpoints for Supabase Edge Functions.

## Quick Start

### Option 1: Docker (Recommended)

```bash
cd ml

# Copy and configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Build and start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Or use Makefile
make up
make logs
```

The API will be available at `http://localhost:8000`

See `DOCKER_SETUP.md` for detailed Docker instructions.

### Option 2: Local Development

#### 1. Install Dependencies

```bash
cd ml
pip install -r requirements.txt
```

#### 2. Configure Environment

Create `.env` file in `ml/` directory:

```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

#### 3. Run Server

```bash
# Development (with auto-reload)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Test

```bash
# Health check
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
# Or visit http://localhost:8000/docs in your browser
```

## API Endpoints

### Technical Indicators
- `GET /api/v1/technical-indicators?symbol=AAPL&timeframe=d1`

### Backtesting
- `POST /api/v1/backtest-strategy`

### Walk-Forward Optimization
- `POST /api/v1/walk-forward-optimize`

### Portfolio Optimization
- `POST /api/v1/portfolio-optimize`

### Stress Testing
- `POST /api/v1/stress-test`

## Project Structure

```
ml/api/
├── main.py                    # FastAPI app entry point
├── routers/                   # API route handlers
│   ├── technical_indicators.py
│   ├── backtest.py
│   ├── walk_forward.py
│   ├── portfolio.py
│   └── stress_test.py
└── models/                    # Pydantic request/response models
    ├── technical_indicators.py
    ├── backtest.py
    ├── walk_forward.py
    ├── portfolio.py
    └── stress_test.py
```

## Development

### Run Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black api/
isort api/
```

## Deployment

See `docs/FASTAPI_SERVER_SETUP.md` for deployment options (Railway, Render, AWS, Docker).

## Environment Variables

- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `FASTAPI_ENV`: Environment (development, production)
- `LOG_LEVEL`: Logging level (info, debug, warning)
