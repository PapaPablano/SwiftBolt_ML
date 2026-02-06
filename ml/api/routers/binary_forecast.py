"""Binary forecast API: generate up/down forecasts and write to ml_forecasts for chart overlay.

POST /api/v1/forecast/binary: body { symbol, horizons: [1, 5, 10] }.
Generates forecasts per horizon, upserts to ml_forecasts (model_type=binary, timeframe=d1),
returns { symbol, horizons: [{ horizon_days, label, confidence, probabilities }] }.
"""

import logging
import sys
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ml_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ml_dir))

from src.data.supabase_db import db
from src.models.binary_forecaster import BinaryForecaster

logger = logging.getLogger(__name__)
router = APIRouter()

HORIZONS_DEFAULT = [1, 5, 10]
MIN_BARS = 200
MIN_SAMPLES = 100


class BinaryForecastRequest(BaseModel):
    """Request body for POST /forecast/binary."""

    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    horizons: list[int] = Field(
        default_factory=lambda: [1, 5, 10],
        description="Forecast horizons in calendar days (e.g. 1, 5, 10)",
    )


class HorizonForecast(BaseModel):
    """One horizon's forecast for the response."""

    horizon_days: int
    label: str  # 'up' | 'down'
    confidence: float
    probabilities: dict[str, float]  # { 'up': float, 'down': float }


class BinaryForecastResponse(BaseModel):
    """Response for POST /forecast/binary."""

    symbol: str
    horizons: list[HorizonForecast]


def _generate_binary_forecasts_for_symbol(symbol: str, horizons: list[int]) -> list[HorizonForecast]:
    """
    Fetch OHLC, train BinaryForecaster per horizon, predict, and upsert to ml_forecasts.

    Returns list of HorizonForecast for the API response.
    """
    symbol = symbol.upper().strip()
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=1000)
    if df is None or len(df) == 0:
        raise ValueError(f"No OHLC data found for {symbol}")

    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    if len(df) < MIN_BARS:
        raise ValueError(f"Not enough history for {symbol} (need >= {MIN_BARS} bars, got {len(df)})")

    symbol_id = db.get_symbol_id(symbol)
    last_ts = df["ts"].iloc[-1]
    last_close = float(df["close"].iloc[-1])
    last_ts_unix = int(pd.Timestamp(last_ts).timestamp())

    results: list[HorizonForecast] = []

    for horizon_days in horizons:
        if horizon_days < 1:
            continue
        try:
            model = BinaryForecaster()
            X, y = model.prepare_training_data(df, horizon_days=horizon_days)
            if len(X) < MIN_SAMPLES:
                logger.warning(
                    "Insufficient samples for %s horizon %dD (got %d), skipping",
                    symbol,
                    horizon_days,
                    len(X),
                )
                continue

            model.train(X, y, min_samples=50)
            pred = model.predict(df, horizon_days=horizon_days)

            label = pred["label"]
            confidence = float(pred["confidence"])
            prob_up = float(pred["probabilities"]["up"])
            prob_down = float(pred["probabilities"]["down"])

            # Map to ml_forecasts: overall_label Bullish/Bearish (DB may expect capitalized or lowercase)
            overall_label = "Bullish" if label == "up" else "Bearish"

            # Target timestamp for chart overlay (same as today: last_ts + horizon_days)
            target_ts_unix = last_ts_unix + horizon_days * 24 * 60 * 60
            horizon_key = f"{horizon_days}D"

            # True level: from non-binary forecast for same symbol/horizon (strict priority: ensemble > xgboost > tabpfn)
            true_level = last_close
            for model_type in ("ensemble", "xgboost", "tabpfn"):
                try:
                    response = (
                        db.client.table("ml_forecasts")
                        .select("points,run_at")
                        .eq("symbol_id", symbol_id)
                        .eq("timeframe", "d1")
                        .eq("horizon", horizon_key)
                        .eq("model_type", model_type)
                        .order("run_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    if not response.data or len(response.data) == 0:
                        continue
                    row = response.data[0]
                    pts = row.get("points") or []
                    for p in pts:
                        ts_val = p.get("ts")
                        if ts_val is None:
                            continue
                        ts_sec = int(ts_val) // 1000 if ts_val > 1e12 else int(ts_val)
                        if ts_sec == target_ts_unix:
                            true_level = float(p.get("value", last_close))
                            break
                    else:
                        if pts:
                            true_level = float(pts[-1].get("value", last_close))
                    break  # found a row for this priority tier
                except Exception as exc:
                    logger.debug(
                        "No %s forecast for true_level (%s %s): %s",
                        model_type,
                        symbol,
                        horizon_key,
                        exc,
                    )
                    continue

            band = 0.01
            points = [
                {
                    "ts": target_ts_unix,
                    "value": true_level,
                    "lower": true_level * (1 - band),
                    "upper": true_level * (1 + band),
                }
            ]
            forecast_return = (true_level / last_close) - 1.0 if last_close else None

            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=horizon_key,
                overall_label=overall_label,
                confidence=confidence,
                points=points,
                forecast_return=forecast_return,
                timeframe="d1",
                model_type="binary",
            )

            results.append(
                HorizonForecast(
                    horizon_days=horizon_days,
                    label=label,
                    confidence=confidence,
                    probabilities={"up": prob_up, "down": prob_down},
                )
            )
        except Exception as exc:
            logger.warning("Error generating %dD forecast for %s: %s", horizon_days, symbol, exc)
            continue

    return results


@router.post("/binary", response_model=BinaryForecastResponse)
async def post_forecast_binary(request: BinaryForecastRequest) -> BinaryForecastResponse:
    """
    Generate binary (up/down) forecasts for a symbol and horizons, write to ml_forecasts, return summary.

    Uses BinaryForecaster; writes to ml_forecasts with model_type=binary, timeframe=d1,
    horizons 1D/5D/10D so chart-data-v2 and SwiftUI can show the overlay.
    """
    symbol = request.symbol.upper().strip()
    horizons = [h for h in request.horizons if 1 <= h <= 20]
    if not horizons:
        horizons = HORIZONS_DEFAULT

    try:
        results = _generate_binary_forecasts_for_symbol(symbol, horizons)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not results:
        raise HTTPException(
            status_code=400,
            detail=f"Could not generate any forecasts for {symbol} (insufficient data or samples)",
        )

    return BinaryForecastResponse(symbol=symbol, horizons=results)
