"""
FastAPI server for ML endpoints.
Exposes ML Python scripts as REST APIs for Supabase Edge Functions.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (
    backtest,
    portfolio,
    stress_test,
    technical_indicators,
    walk_forward,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info("Starting FastAPI server...")
    yield
    logger.info("Shutting down FastAPI server...")


# Create FastAPI app
app = FastAPI(
    title="SwiftBolt ML API",
    description="REST API for ML-powered trading analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
# In production, restrict origins to your Supabase Edge Function URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(technical_indicators.router, prefix="/api/v1", tags=["Technical Indicators"])
app.include_router(backtest.router, prefix="/api/v1", tags=["Backtesting"])
app.include_router(walk_forward.router, prefix="/api/v1", tags=["Walk-Forward Optimization"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["Portfolio Optimization"])
app.include_router(stress_test.router, prefix="/api/v1", tags=["Stress Testing"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SwiftBolt ML API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
