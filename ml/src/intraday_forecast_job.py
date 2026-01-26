"""Intraday ML forecasting job for weight calibration.

Generates 15-minute and 1-hour forecasts that can be rapidly evaluated
to learn optimal layer weights for the main daily forecast system.
"""

import argparse
import logging
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

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
from src.models.arima_garch_forecaster import ArimaGarchForecaster  # noqa: E402
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.services.forecast_bar_writer import (  # noqa: E402
    path_points_to_bars,
    upsert_forecast_bars,
)
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402
from src.models.enhanced_ensemble_integration import get_production_ensemble  # noqa: E402
from src.intraday_daily_feedback import IntradayDailyFeedback  # noqa: E402
from src.features.timeframe_consensus import add_consensus_to_forecast  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Mapping from horizon to timeframe and bars
HORIZON_CONFIG = {
    # Existing short-term horizons (use basic ensemble for speed)
    "15m": {
        "timeframe": "m15",
        "bars_per_hour": 4,
        "forecast_bars": 1,  # 1 bar ahead = 15 minutes
        "min_training_bars": 60,  # ~1 trading day (reduced from 100)
        "indicator_scale": 0.25,  # Scale down indicator periods
        "use_advanced_ensemble": False,  # Keep basic for speed
    },
    "1h": {
        "timeframe": "h1",
        "bars_per_hour": 1,
        "forecast_bars": 1,  # 1 bar ahead = 1 hour
        "min_training_bars": 60,  # ~1.5 trading weeks (reduced from 100)
        "indicator_scale": 0.5,
        "use_advanced_ensemble": False,  # Keep basic for speed
    },
    # NEW: Medium-term horizons with advanced 4-model ensemble
    "4h": {
        "timeframe": "h4",
        "bars_per_hour": 0.25,
        "forecast_bars": 1,  # 1 bar ahead = 4 hours
        "min_training_bars": 100,  # ~2 months (reduced from 200)
        "indicator_scale": 1.0,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "horizon_days": 0.167,  # 4/24 hours
    },
    "8h": {
        "timeframe": "h8",
        "bars_per_hour": 0.125,
        "forecast_bars": 1,  # 1 bar ahead = 8 hours
        "min_training_bars": 120,  # ~2.5 months (reduced from 250)
        "indicator_scale": 1.5,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "horizon_days": 0.333,  # 8/24 hours
    },
    "1D": {
        "timeframe": "d1",
        "forecast_bars": 1,  # 1 bar ahead = 1 day
        "min_training_bars": 200,  # ~10 months (reduced from 500)
        "indicator_scale": 2.0,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "horizon_days": 1.0,  # 1 day
    },
}


def timeframe_interval_seconds(timeframe: str) -> int:
    if timeframe == "m15":
        return 15 * 60
    if timeframe == "h1":
        return 60 * 60
    if timeframe == "h4":
        return 4 * 60 * 60
    if timeframe == "h8":
        return 8 * 60 * 60
    if timeframe == "d1":
        return 24 * 60 * 60
    raise ValueError(f"Unknown timeframe: {timeframe}")


def _aggregate_h4_to_h8(h4_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 4-hour bars into 8-hour bars.
    
    Groups every 2 consecutive h4 bars into 1 h8 bar:
    - open: first bar's open
    - high: max of both bars' highs
    - low: min of both bars' lows
    - close: last bar's close
    - volume: sum of both bars' volumes
    - ts: first bar's timestamp
    
    Args:
        h4_df: DataFrame with h4 OHLC bars (must have ts, open, high, low, close, volume)
    
    Returns:
        DataFrame with h8 OHLC bars
    """
    if len(h4_df) < 2:
        return pd.DataFrame()
    
    # Ensure ts is datetime
    if "ts" in h4_df.columns:
        h4_df = h4_df.copy()
        if not pd.api.types.is_datetime64_any_dtype(h4_df["ts"]):
            h4_df["ts"] = pd.to_datetime(h4_df["ts"])
        h4_df = h4_df.sort_values("ts").reset_index(drop=True)
    
    h8_rows = []
    for i in range(0, len(h4_df) - 1, 2):  # Process pairs
        bar1 = h4_df.iloc[i]
        bar2 = h4_df.iloc[i + 1]
        
        h8_rows.append({
            "ts": bar1["ts"],
            "open": float(bar1["open"]),
            "high": max(float(bar1["high"]), float(bar2["high"])),
            "low": min(float(bar1["low"]), float(bar2["low"])),
            "close": float(bar2["close"]),
            "volume": float(bar1.get("volume", 0) or 0) + float(bar2.get("volume", 0) or 0),
        })
    
    if not h8_rows:
        return pd.DataFrame()
    
    h8_df = pd.DataFrame(h8_rows)
    return h8_df


def get_weight_source_for_intraday(symbol: str, symbol_id: str, horizon: str, use_feedback: bool) -> tuple:
    """
    Get forecast layer weights with optional feedback loop integration.

    Args:
        symbol: Symbol ticker
        symbol_id: Symbol UUID
        horizon: Forecast horizon (4h, 8h, 1D)
        use_feedback: Whether to use IntradayDailyFeedback (True for 4h/8h/1D)

    Returns:
        (ForecastWeights object, source_name)
    """
    if not use_feedback:
        # For 15m/1h: always use defaults (they're for calibration)
        return get_default_weights(), 'default'

    try:
        # For 4h/8h/1D: use IntradayDailyFeedback priority system
        feedback_loop = IntradayDailyFeedback()
        weights_obj, source = feedback_loop.get_best_weights(symbol, horizon)
        logger.debug(f"Using weights from {source} for {symbol} {horizon}")
        return weights_obj, source
    except Exception as e:
        logger.warning(f"IntradayDailyFeedback failed for {symbol} {horizon}: {e}. Using defaults.")
        return get_default_weights(), 'default (fallback)'


def build_intraday_short_points(
    *,
    base_ts_sec: int,
    interval_sec: int,
    steps: int,
    current_price: float,
    target_price: float,
    confidence: float,
) -> list[dict]:
    safe_steps = max(1, min(500, int(steps)))
    conf = float(np.clip(confidence, 0.0, 1.0))
    band_pct = float(np.clip(0.03 - conf * 0.02, 0.005, 0.04))

    points: list[dict] = []
    for i in range(0, safe_steps + 1):
        t = i / safe_steps
        value = float(current_price + (target_price - current_price) * t)
        lower = float(value * (1.0 - band_pct))
        upper = float(value * (1.0 + band_pct))
        points.append(
            {
                "ts": int(base_ts_sec + interval_sec * i),
                "value": round(value, 4),
                "lower": round(lower, 4),
                "upper": round(upper, 4),
            }
        )
    return points


def build_intraday_path_points(
    df,
    *,
    steps: int,
    interval_sec: int,
    confidence: float,
) -> list[dict]:
    closes = df["close"].astype(float)
    returns = closes.pct_change().dropna()
    last_close = float(closes.iloc[-1])
    last_ts = df["ts"].iloc[-1]
    last_dt = pd.to_datetime(last_ts, utc=True).to_pydatetime()
    et = ZoneInfo("America/New_York")
    open_t = time(9, 30)
    close_t = time(16, 0)

    def next_trading_dt(dt_utc: datetime) -> datetime:
        candidate = dt_utc
        while True:
            local = candidate.astimezone(et)

            if local.weekday() >= 5:
                days_ahead = 7 - local.weekday()
                local = (local + timedelta(days=days_ahead)).replace(
                    hour=open_t.hour,
                    minute=open_t.minute,
                    second=0,
                    microsecond=0,
                )
                candidate = local.astimezone(timezone.utc)
                continue

            if local.time() < open_t:
                local = local.replace(
                    hour=open_t.hour,
                    minute=open_t.minute,
                    second=0,
                    microsecond=0,
                )
                candidate = local.astimezone(timezone.utc)
                continue

            if local.time() > close_t:
                local = (local + timedelta(days=1)).replace(
                    hour=open_t.hour,
                    minute=open_t.minute,
                    second=0,
                    microsecond=0,
                )
                candidate = local.astimezone(timezone.utc)
                continue

            return candidate

    try:
        forecaster = ArimaGarchForecaster(
            arima_order=(1, 0, 1),
            auto_select_order=False,
            bullish_threshold=0.002,
            bearish_threshold=-0.002,
        )
        forecaster.train(df, min_samples=100)

        forecast_result = forecaster.fitted_arima.get_forecast(steps=steps)
        step_returns = forecast_result.predicted_mean.values
        step_returns = np.array(step_returns, dtype=float)
        if step_returns.ndim != 1 or len(step_returns) != steps:
            raise ValueError("Unexpected ARIMA forecast shape")
        cum_returns = np.cumsum(step_returns)
        base_vol = float(max(1e-6, returns.std()))
    except Exception as exc:
        logger.warning("Path forecast fallback: %s", exc)
        step_returns = np.zeros(steps, dtype=float)
        cum_returns = np.cumsum(step_returns)
        base_vol = float(max(1e-6, returns.std()))

    conf = float(np.clip(confidence, 0.0, 1.0))

    points: list[dict] = []
    cursor = next_trading_dt(last_dt)
    for i in range(1, steps + 1):
        progress = float(i)
        value = last_close * (1.0 + float(cum_returns[i - 1]))
        z = 1.96
        sigma = base_vol * np.sqrt(progress)
        band = z * sigma * (1.2 - 0.8 * conf)
        lower = value * (1.0 - band)
        upper = value * (1.0 + band)
        cursor = next_trading_dt(cursor + timedelta(seconds=interval_sec))
        ts = int(cursor.timestamp())
        points.append(
            {
                "ts": ts,
                "value": round(float(value), 4),
                "lower": round(float(lower), 4),
                "upper": round(float(upper), 4),
            }
        )
    return points


def get_expiry_time(horizon: str) -> datetime:
    """Calculate when the forecast expires based on horizon."""
    now = datetime.utcnow().replace(second=0, microsecond=0)

    if horizon == "15m":
        expiry = now + timedelta(minutes=30)
    elif horizon == "1h":
        expiry = now + timedelta(hours=2)
    elif horizon == "4h":
        expiry = now + timedelta(hours=6)
    elif horizon == "8h":
        expiry = now + timedelta(hours=12)
    elif horizon == "1D":
        expiry = now + timedelta(hours=24)
    else:
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
        "anchorZones": sr_levels.get("anchor_zones", {}),
        "movingAverages": (sr_levels.get("moving_averages") or {}).get("levels", []),
        "fibonacci": sr_levels.get("fibonacci", {}),
        "ichimoku": sr_levels.get("ichimoku", {}),
    }


def convert_supertrend_to_synthesizer_format(st_info: dict) -> dict:
    """Convert SuperTrend output to synthesizer format."""
    return {
        "current_trend": st_info.get("current_trend", "NEUTRAL"),
        "signal_strength": st_info.get("signal_strength", 5),
        "performance_index": st_info.get("performance_index", 0.5),
        "atr": st_info.get("atr"),
    }


def process_symbol_intraday(symbol: str, horizon: str, *, generate_paths: bool) -> bool:
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
        df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=min_bars)

        # Fallback: For h8 timeframe, try aggregating from h4 if no h8 data available
        if len(df) == 0 and timeframe == "h8":
            logger.info("No h8 data for %s, attempting to aggregate from h4...", symbol)
            h4_df = db.fetch_ohlc_bars(symbol, timeframe="h4", limit=min_bars * 2)
            if len(h4_df) >= 2:
                # Aggregate 2 h4 bars into 1 h8 bar
                df = _aggregate_h4_to_h8(h4_df)
                logger.info("Aggregated %d h4 bars to %d h8 bars for %s", len(h4_df), len(df), symbol)
            else:
                logger.warning("Insufficient h4 data to aggregate h8 for %s: %d bars", symbol, len(h4_df))

        if len(df) < min_bars:
            logger.warning(
                "Insufficient %s bars for %s: %d (need %d). Proceeding with fallback.",
                timeframe,
                symbol,
                len(df),
                min_bars,
            )
            if len(df) < 30:
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

        # === Save Indicator Snapshot for Intraday ===
        try:
            # Save fewer bars for intraday (last 20)
            snapshot_bars = min(len(df), 20)
            indicator_records = []

            for idx in range(-snapshot_bars, 0):
                row = df.iloc[idx]
                record = {
                    "ts": row.get("ts") if "ts" in df.columns else row.name,
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    # Momentum indicators
                    "rsi_14": row.get("rsi_14"),
                    "macd": row.get("macd"),
                    "macd_signal": row.get("macd_signal"),
                    "macd_hist": row.get("macd_hist"),
                    # ADX
                    "adx": row.get("adx"),
                    "atr_14": row.get("atr_14"),
                    # Volatility bands
                    "bb_upper": row.get("bb_upper"),
                    "bb_lower": row.get("bb_lower"),
                    # Additional momentum/trend
                    "stoch_k": row.get("stoch_k"),
                    "stoch_d": row.get("stoch_d"),
                    "williams_r": row.get("williams_r"),
                    "cci": row.get("cci"),
                    "mfi": row.get("mfi") or row.get("mfi_14"),
                    "obv": row.get("obv"),
                    # SuperTrend AI features
                    "supertrend_factor": row.get("supertrend_factor")
                    or row.get("supertrend_adaptive_factor")
                    or row.get("target_factor"),
                    "supertrend_performance_index": row.get(
                        "supertrend_performance_index"
                    ),
                    "supertrend_signal_strength": row.get(
                        "supertrend_signal_strength"
                    ),
                    "signal_confidence": row.get("signal_confidence"),
                    "supertrend_confidence_norm": row.get(
                        "supertrend_confidence_norm"
                    ),
                    "supertrend_distance_norm": row.get(
                        "supertrend_distance_norm"
                    ),
                    "perf_ama": row.get("perf_ama"),
                }

                # Add SuperTrend if available
                if "supertrend" in df.columns:
                    record["supertrend_value"] = row.get("supertrend")
                    record["supertrend_trend"] = (
                        1 if row.get("supertrend_signal", 0) > 0 else 0
                    )

                indicator_records.append(record)

            # Add S/R levels to most recent record
            if indicator_records and sr_levels:
                indicator_records[-1]["nearest_support"] = sr_levels.get(
                    "nearest_support"
                )
                indicator_records[-1]["nearest_resistance"] = sr_levels.get(
                    "nearest_resistance"
                )
                indicator_records[-1]["support_distance_pct"] = sr_levels.get(
                    "support_distance_pct"
                )
                indicator_records[-1]["resistance_distance_pct"] = sr_levels.get(
                    "resistance_distance_pct"
                )

            # Map timeframe to db format (h1 -> h1, m15 -> m15)
            db_timeframe = timeframe  # Already in correct format
            db.save_indicator_snapshot(
                symbol_id=symbol_id,
                timeframe=db_timeframe,
                indicators=indicator_records,
            )

        except Exception as e:
            logger.warning(
                "Failed to save intraday indicator snapshot for %s: %s", symbol, e
            )

        # Determine if we use advanced ensemble based on horizon config
        use_advanced = config.get("use_advanced_ensemble", False)
        horizon_days = config.get("horizon_days", 1.0)

        # Get layer weights (feedback-based for 4h/8h/1D, defaults for 15m/1h)
        weights, weight_source = get_weight_source_for_intraday(
            symbol=symbol,
            symbol_id=symbol_id,
            horizon=horizon,
            use_feedback=use_advanced,
        )

        # Prepare training data
        baseline = BaselineForecaster()
        try:
            X, y = baseline.prepare_training_data(df, horizon_days=horizon_days)
        except Exception as e:
            logger.warning("Training data prep failed for %s: %s", symbol, e)
            X = pd.DataFrame()
            y = pd.Series(dtype=str)

        ensemble_pred = None
        min_bars = config.get("min_training_bars", 50)
        if len(X) >= min_bars:
            unique_labels = y.unique() if hasattr(y, "unique") else np.unique(y)
            if len(unique_labels) > 1:
                try:
                    if use_advanced:
                        # ADVANCED ENSEMBLE: 4-6 model ensemble with OHLC data
                        ensemble = get_production_ensemble(
                            horizon=horizon,
                            symbol_id=symbol_id,
                        )

                        # Align OHLC data with features (pattern from unified_forecast_job.py)
                        min_offset = 50 if len(df) >= 100 else (26 if len(df) >= 60 else 14)
                        start_idx = max(min_offset, 14)
                        end_idx = len(df) - max(1, int(horizon_days))
                        ohlc_train = df.iloc[start_idx:end_idx].copy()

                        # Train with OHLC data (required for ARIMA-GARCH, Prophet)
                        ensemble.train(
                            features_df=X,
                            labels_series=y,
                            ohlc_df=ohlc_train,
                        )

                        # Predict with OHLC data
                        ensemble_pred = ensemble.predict(
                            features_df=X.tail(1),
                            ohlc_df=df.tail(1),
                        )

                        logger.info(
                            f"Advanced ensemble for {symbol} {horizon}: "
                            f"{ensemble_pred.get('label', 'unknown').upper()} "
                            f"({ensemble_pred.get('confidence', 0):.0%}, "
                            f"n_models={ensemble_pred.get('n_models', 0)})"
                        )
                    else:
                        # BASIC ENSEMBLE: Existing 5-model for 15m/1h (fast)
                        forecaster = EnsembleForecaster(horizon="1D", symbol_id=symbol_id)
                        forecaster.train(X, y)
                        last_features = X.tail(1)
                        ensemble_pred = forecaster.predict(last_features)

                except Exception as e:
                    logger.warning("Ensemble training failed for %s: %s", symbol, e)
        else:
            logger.warning(
                "Insufficient training samples for %s: %d (need %d). Using fallback.",
                symbol,
                len(X),
                min_bars,
            )

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

        # Use ForecastSynthesizer with weights from feedback loop or defaults
        synthesizer = ForecastSynthesizer(weights=weights)
        sr_response = convert_sr_to_synthesizer_format(sr_levels, current_price)
        supertrend_for_synth = convert_supertrend_to_synthesizer_format(st_info_raw)

        # Use generate_forecast() with horizon_days parameter (scales ATR moves)
        synth_result = synthesizer.generate_forecast(
            current_price=current_price,
            df=df,
            supertrend_info=supertrend_for_synth,
            sr_response=sr_response,
            ensemble_result=ensemble_pred,
            symbol=symbol,
            horizon_days=horizon_days,  # NEW: scales volatility by sqrt(time)
            timeframe=timeframe,
        )

        try:
            last_ts = df["ts"].iloc[-1]
            base_ts_sec = int(pd.to_datetime(last_ts, utc=True).timestamp())
        except Exception:
            base_ts_sec = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())

        horizon_seconds_map = {
            "15m": 15 * 60,
            "1h": 60 * 60,
            "4h": 4 * 60 * 60,
            "8h": 8 * 60 * 60,
            "1D": 24 * 60 * 60,
        }
        horizon_seconds = int(
            horizon_seconds_map.get(horizon, timeframe_interval_seconds(timeframe))
        )

        short_steps_by_horizon = {
            "15m": 8,
            "1h": 12,
            "4h": 16,
            "8h": 24,
            "1D": 24,
        }
        short_steps = int(short_steps_by_horizon.get(horizon, 8))
        short_interval_sec = max(1, int(round(horizon_seconds / max(1, short_steps))))
        short_points = build_intraday_short_points(
            base_ts_sec=base_ts_sec,
            interval_sec=short_interval_sec,
            steps=short_steps,
            current_price=float(current_price),
            target_price=float(synth_result.target),
            confidence=float(synth_result.confidence),
        )

        # Calculate expiry time
        expires_at = get_expiry_time(horizon)

        # Build initial forecast dict for consensus scoring
        forecast_dict = {
            "label": synth_result.direction.lower(),
            "confidence": synth_result.confidence,
            "horizon": horizon,
            "timeframe": timeframe,
            "target_price": synth_result.target,
            "current_price": current_price,
            "weight_source": weight_source,
        }

        # Add consensus scoring for advanced ensemble horizons (4h, 8h, 1D)
        consensus_direction = synth_result.direction.lower()
        alignment_score = 0.0
        adjusted_confidence = synth_result.confidence
        if use_advanced:
            try:
                forecast_dict = add_consensus_to_forecast(forecast_dict, symbol_id)
                consensus_direction = forecast_dict.get('consensus_direction', synth_result.direction.lower())
                alignment_score = forecast_dict.get('alignment_score', 0.0)
                adjusted_confidence = forecast_dict.get('adjusted_confidence', synth_result.confidence)
                logger.debug(
                    f"Consensus for {symbol} {horizon}: "
                    f"{consensus_direction} "
                    f"(alignment={alignment_score:.2f})"
                )
            except Exception as e:
                logger.warning(f"Consensus scoring failed for {symbol} {horizon}: {e}")

        # Save intraday forecast (single-target)
        forecast_id = db.upsert_intraday_forecast(
            symbol_id=symbol_id,
            symbol=symbol,
            horizon=horizon,
            timeframe=timeframe,
            overall_label=consensus_direction,
            confidence=adjusted_confidence,
            points=short_points,
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
            if generate_paths and horizon == "1h":
                try:
                    path_days = int(getattr(settings, "intraday_path_days", 7))
                except Exception:
                    path_days = 7

                path_horizon = f"{path_days}d"

                path_points_by_tf: dict[str, list[dict]] = {}
                for tf in ["m15", "h1", "h4"]:
                    interval_sec = timeframe_interval_seconds(tf)
                    steps_per_day = int(round((6.5 * 60 * 60) / interval_sec))
                    steps = max(8, min(500, steps_per_day * path_days))

                    path_df = db.fetch_ohlc_bars(symbol, timeframe=tf, limit=max(300, steps * 4))
                    if path_df is None or len(path_df) < 120:
                        continue

                    path_points = build_intraday_path_points(
                        path_df,
                        steps=steps,
                        interval_sec=interval_sec,
                        confidence=synth_result.confidence,
                    )

                    path_points_by_tf[tf] = path_points

                    expires_at_path = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
                    db.insert_intraday_forecast_path(
                        symbol_id=symbol_id,
                        symbol=symbol,
                        timeframe=tf,
                        horizon=path_horizon,
                        steps=steps,
                        interval_sec=interval_sec,
                        overall_label=synth_result.direction.lower(),
                        confidence=synth_result.confidence,
                        model_type="arima_garch",
                        points=path_points,
                        expires_at=expires_at_path,
                    )

                source_points = (
                    path_points_by_tf.get("m15")
                    or path_points_by_tf.get("h1")
                    or path_points_by_tf.get("h4")
                )

                if source_points:
                    for tf in ["m15", "h1", "h4", "d1", "w1"]:
                        rows = path_points_to_bars(points=source_points, timeframe=tf)
                        for row in rows:
                            row["confidence_score"] = float(synth_result.confidence)

                        upsert_forecast_bars(
                            symbol=symbol,
                            timeframe=tf,
                            rows=rows,
                            status="provisional",
                            skip_non_future_dates=True,
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
        choices=["15m", "1h", "4h", "8h", "1D"],
        required=True,
        help="Forecast horizon (15m, 1h, 4h, 8h, or 1D)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Single symbol to process (default: all intraday symbols)",
    )
    parser.add_argument(
        "--generate-paths",
        action="store_true",
        help="Generate and store a multi-step intraday path forecast (e.g., 7d)",
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
        if process_symbol_intraday(symbol, args.horizon, generate_paths=args.generate_paths):
            success_count += 1
        else:
            fail_count += 1

    logger.info("=" * 60)
    logger.info("Intraday Forecast Job Complete")
    logger.info("Success: %d, Failed: %d", success_count, fail_count)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
