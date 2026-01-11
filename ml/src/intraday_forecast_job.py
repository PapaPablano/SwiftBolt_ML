"""Intraday ML forecasting job for weight calibration.

Generates 15-minute and 1-hour forecasts that can be rapidly evaluated
to learn optimal layer weights for the main daily forecast system.
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.features.support_resistance_detector import (  # noqa: E402
    SupportResistanceDetector,
)
from src.features.technical_indicators import add_technical_features  # noqa: E402
from src.forecast_synthesizer import ForecastSynthesizer  # noqa: E402
from src.forecast_weights import get_default_weights  # noqa: E402
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Mapping from horizon to timeframe and bars
HORIZON_CONFIG = {
    "15m": {
        "timeframe": "m15",
        "bars_per_hour": 4,
        "forecast_bars": 1,  # 1 bar ahead = 15 minutes
        "min_training_bars": 100,
        "indicator_scale": 0.25,  # Scale down indicator periods
    },
    "1h": {
        "timeframe": "h1",
        "bars_per_hour": 1,
        "forecast_bars": 1,  # 1 bar ahead = 1 hour
        "min_training_bars": 100,
        "indicator_scale": 0.5,
    },
}


def get_expiry_time(horizon: str) -> datetime:
    """Calculate when the forecast expires based on horizon."""
    now = datetime.utcnow()

    if horizon == "15m":
        # Round to next 15-minute mark
        minutes = (now.minute // 15 + 1) * 15
        if minutes >= 60:
            expiry = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            expiry = now.replace(minute=minutes, second=0, microsecond=0)
    elif horizon == "1h":
        # Round to next hour
        expiry = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        # Default to 1 hour
        expiry = now + timedelta(hours=1)

    return expiry


def convert_sr_to_synthesizer_format(
    sr_levels: dict,
    current_price: float,
) -> dict:
    """Convert S/R detector output to synthesizer format."""
    indicators = sr_levels.get("indicators", {})

    poly_in = indicators.get("polynomial", {})
    polynomial = {
        "support": poly_in.get("current_support", current_price * 0.95),
        "resistance": poly_in.get("current_resistance", current_price * 1.05),
        "supportSlope": poly_in.get("support_slope", 0),
        "resistanceSlope": poly_in.get("resistance_slope", 0),
        "supportTrend": "rising" if poly_in.get("support_slope", 0) > 0 else "falling",
        "resistanceTrend": "rising" if poly_in.get("resistance_slope", 0) > 0 else "falling",
        "forecastSupport": poly_in.get("forecast_support", []),
        "forecastResistance": poly_in.get("forecast_resistance", []),
        "isDiverging": poly_in.get("is_diverging", False),
        "isConverging": poly_in.get("is_converging", False),
    }

    logistic_in = indicators.get("logistic", {})
    logistic = {
        "supportLevels": [
            {"level": lvl.get("level", 0), "probability": lvl.get("probability", 0.5)}
            for lvl in logistic_in.get("support_levels", [])
        ],
        "resistanceLevels": [
            {"level": lvl.get("level", 0), "probability": lvl.get("probability", 0.5)}
            for lvl in logistic_in.get("resistance_levels", [])
        ],
        "signals": logistic_in.get("signals", []),
    }

    pivot_in = indicators.get("pivot_levels", {})
    pivot_levels_list = pivot_in.get("pivot_levels", [])
    pivot_levels = {}
    for pl in pivot_levels_list:
        period = pl.get("period", 5)
        key = f"period{period}"
        pivot_levels[key] = {
            "high": pl.get("high"),
            "low": pl.get("low"),
            "highStatus": pl.get("high_status", "active"),
            "lowStatus": pl.get("low_status", "active"),
        }

    for period in [5, 25, 50, 100]:
        key = f"period{period}"
        if key not in pivot_levels:
            pivot_levels[key] = {
                "high": current_price * 1.02,
                "low": current_price * 0.98,
                "highStatus": "active",
                "lowStatus": "active",
            }

    return {
        "pivotLevels": pivot_levels,
        "polynomial": polynomial,
        "logistic": logistic,
        "nearestSupport": sr_levels.get("nearest_support", current_price * 0.95),
        "nearestResistance": sr_levels.get("nearest_resistance", current_price * 1.05),
    }


def convert_supertrend_to_synthesizer_format(st_info: dict) -> dict:
    """Convert SuperTrend output to synthesizer format."""
    return {
        "current_trend": st_info.get("current_trend", "NEUTRAL"),
        "signal_strength": st_info.get("signal_strength", 5),
        "performance_index": st_info.get("performance_index", 0.5),
        "atr": st_info.get("atr"),
    }


def process_symbol_intraday(symbol: str, horizon: str) -> bool:
    """
    Generate an intraday forecast for a single symbol.

    Args:
        symbol: Stock ticker symbol
        horizon: '15m' or '1h'

    Returns:
        True if forecast was generated successfully
    """
    config = HORIZON_CONFIG.get(horizon)
    if not config:
        logger.error("Invalid horizon: %s", horizon)
        return False

    timeframe = config["timeframe"]
    min_bars = config["min_training_bars"]

    logger.info("Processing %s intraday forecast for %s", horizon, symbol)

    try:
        # Fetch intraday bars
        df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=min_bars * 2)

        if len(df) < min_bars:
            logger.warning(
                "Insufficient %s bars for %s: %d (need %d)",
                timeframe,
                symbol,
                len(df),
                min_bars,
            )
            return False

        # Get symbol ID
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            logger.error("Symbol not found: %s", symbol)
            return False

        # Add technical indicators (will auto-scale for intraday)
        df = add_technical_features(df)

        # Extract S/R levels
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        current_price = df["close"].iloc[-1]

        # SuperTrend AI
        st_info_raw = None
        try:
            supertrend = SuperTrendAI(df)
            _, st_info_raw = supertrend.calculate()
        except Exception as e:
            logger.warning("SuperTrend failed for %s: %s", symbol, e)
            st_info_raw = {
                "current_trend": "NEUTRAL",
                "signal_strength": 5,
                "performance_index": 0.5,
                "atr": current_price * 0.01,
            }

        # Train simplified ensemble for intraday
        baseline = BaselineForecaster()
        X, y = baseline.prepare_training_data(df, horizon_days=1)

        if len(X) < 50:
            logger.warning("Insufficient training samples for %s", symbol)
            return False

        # Check label distribution - if only one class, use baseline prediction
        unique_labels = y.unique() if hasattr(y, "unique") else np.unique(y)
        ensemble_pred = None

        if len(unique_labels) > 1:
            try:
                forecaster = EnsembleForecaster(horizon="1D", symbol_id=symbol_id)
                forecaster.train(X, y)
                last_features = X.tail(1)
                ensemble_pred = forecaster.predict(last_features)
            except Exception as e:
                logger.warning("Ensemble training failed for %s: %s", symbol, e)

        # Fallback: use technical indicator based prediction
        if ensemble_pred is None:
            # Calculate simple momentum-based prediction
            returns = df["close"].pct_change().tail(20)
            avg_return = returns.mean()
            if avg_return > 0.002:
                label = "bullish"
                confidence = min(0.7, 0.5 + abs(avg_return) * 10)
            elif avg_return < -0.002:
                label = "bearish"
                confidence = min(0.7, 0.5 + abs(avg_return) * 10)
            else:
                label = "neutral"
                confidence = 0.5

            ensemble_pred = {
                "label": label,
                "confidence": confidence,
                "agreement": True,
                "probabilities": {label: confidence},
            }
            logger.info(
                "Using momentum fallback for %s: %s (%.1f%%)",
                symbol,
                label,
                confidence * 100,
            )

        # Use ForecastSynthesizer
        synthesizer = ForecastSynthesizer(weights=get_default_weights())
        sr_response = convert_sr_to_synthesizer_format(sr_levels, current_price)
        supertrend_for_synth = convert_supertrend_to_synthesizer_format(st_info_raw)

        synth_result = synthesizer.generate_1d_forecast(
            current_price=current_price,
            df=df,
            supertrend_info=supertrend_for_synth,
            sr_response=sr_response,
            ensemble_result=ensemble_pred,
            symbol=symbol,
        )

        # Calculate expiry time
        expires_at = get_expiry_time(horizon)

        # Save intraday forecast
        forecast_id = db.upsert_intraday_forecast(
            symbol_id=symbol_id,
            symbol=symbol,
            horizon=horizon,
            timeframe=timeframe,
            overall_label=synth_result.direction.lower(),
            confidence=synth_result.confidence,
            target_price=synth_result.target,
            current_price=current_price,
            supertrend_component=synth_result.supertrend_component,
            sr_component=synth_result.polynomial_component,
            ensemble_component=synth_result.ml_component,
            supertrend_direction=st_info_raw.get("current_trend", "NEUTRAL"),
            ensemble_label=ensemble_pred.get("label", "neutral"),
            layers_agreeing=synth_result.layers_agreeing,
            expires_at=expires_at.isoformat(),
        )

        if forecast_id:
            logger.info(
                "Generated %s forecast for %s: %s target=$%.2f conf=%.0f%% expires=%s",
                horizon,
                symbol,
                synth_result.direction,
                synth_result.target,
                synth_result.confidence * 100,
                expires_at.strftime("%H:%M"),
            )
            return True

        return False

    except Exception as e:
        logger.error("Error processing %s for %s: %s", horizon, symbol, e, exc_info=True)
        return False


def main() -> None:
    """Main entry point for intraday forecast job."""
    parser = argparse.ArgumentParser(description="Generate intraday forecasts")
    parser.add_argument(
        "--horizon",
        type=str,
        choices=["15m", "1h"],
        required=True,
        help="Forecast horizon (15m or 1h)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Single symbol to process (default: all intraday symbols)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Intraday Forecast Job")
    logger.info("Horizon: %s", args.horizon)
    logger.info("=" * 60)

    # Get symbols to process
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = settings.intraday_symbols

    success_count = 0
    fail_count = 0

    for symbol in symbols:
        if process_symbol_intraday(symbol, args.horizon):
            success_count += 1
        else:
            fail_count += 1

    logger.info("=" * 60)
    logger.info("Intraday Forecast Job Complete")
    logger.info("Success: %d, Failed: %d", success_count, fail_count)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
