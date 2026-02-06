"""FastAPI service exposing binary up/down forecasts for use by the app charts.

Run with:
    cd /Users/ericpeterson/SwiftBolt_ML/ml
    PYTHONPATH=. uvicorn api.binary_forecast_service:app --reload --port 8001
"""

from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.data.supabase_db import db
from src.models.binary_forecaster import BinaryForecaster

app = FastAPI(title="SwiftBolt Binary Forecast Service", version="1.0.0")


class ForecastRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    horizon_days: int = Field(5, ge=1, le=20, description="Forecast horizon in calendar days")


class ForecastResponse(BaseModel):
    symbol: str
    forecast_date: datetime
    horizon_days: int
    label: Literal["up", "down"]
    confidence: float
    prob_up: float
    prob_down: float


@app.get("/health")
async def health() -> dict:
    """Simple health check for uptime monitoring."""
    return {"status": "ok", "service": "binary_forecast"}


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """Generate a binary (up/down) forecast for a symbol and horizon.

    This endpoint:
      1. Fetches recent daily OHLC bars from Supabase
      2. Trains a BinaryForecaster on the full history
      3. Predicts up/down for the latest bar

    Intended for on-demand use when a user opens a chart in the app.
    """
    symbol = req.symbol.upper().strip()

    # 1) Fetch data
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=1000)
    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail=f"No OHLC data found for {symbol}")

    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    if len(df) < 200:
        raise HTTPException(status_code=400, detail=f"Not enough history for {symbol} (need >=200 bars)")

    # 2) Train model on history
    model = BinaryForecaster()
    X, y = model.prepare_training_data(df, horizon_days=req.horizon_days)

    if len(X) < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient training samples for {symbol} at horizon {req.horizon_days}D (got {len(X)})",
        )

    model.train(X, y, min_samples=50)

    # 3) Predict for latest bar
    pred = model.predict(df, horizon_days=req.horizon_days)

    last_ts = df["ts"].iloc[-1]
    if isinstance(last_ts, pd.Timestamp):
        forecast_date = last_ts.to_pydatetime()
    else:
        forecast_date = datetime.fromisoformat(str(last_ts))

    prob_up = float(pred["probabilities"]["up"])
    prob_down = float(pred["probabilities"]["down"])

    return ForecastResponse(
        symbol=symbol,
        forecast_date=forecast_date,
        horizon_days=req.horizon_days,
        label=pred["label"],
        confidence=float(pred["confidence"]),
        prob_up=prob_up,
        prob_down=prob_down,
    )
