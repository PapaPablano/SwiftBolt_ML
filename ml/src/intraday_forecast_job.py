"""Intraday ML forecasting job for weight calibration.

Generates 15-minute and 1-hour forecasts that can be rapidly evaluated
to learn optimal layer weights for the main daily forecast system.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.features.indicator_recompute import attach_indicators_to_forecast_points  # noqa: E402
from src.features.support_resistance_detector import (  # noqa: E402
    SupportResistanceDetector,
)
from src.features.technical_indicators import add_technical_features  # noqa: E402
from src.forecast_synthesizer import ForecastSynthesizer  # noqa: E402
from src.forecast_weights import get_default_weights  # noqa: E402
from src.models.arima_garch_forecaster import ArimaGarchForecaster  # noqa: E402
from src.models.baseline_forecaster import BASELINE_START_IDX, BaselineForecaster  # noqa: E402
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.models.xgboost_forecaster import XGBoostForecaster  # noqa: E402
from src.models.state_space_kalman_forecaster import (  # noqa: E402
    StateSpaceKalmanForecaster,
)
from src.services.forecast_bar_writer import (  # noqa: E402
    path_points_to_bars,
    upsert_forecast_bars,
)
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402
from src.models.enhanced_ensemble_integration import get_production_ensemble  # noqa: E402
from src.intraday_daily_feedback import IntradayDailyFeedback  # noqa: E402
from src.features.timeframe_consensus import add_consensus_to_forecast  # noqa: E402
from src.strategies.adaptive_supertrend_adapter import (  # noqa: E402
    get_adaptive_supertrend_adapter,
)
from src.monitoring.divergence_monitor import DivergenceMonitor  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Mapping from horizon to timeframe and bars
HORIZON_CONFIG = {
    # Existing short-term horizons (use basic ensemble for speed, no walk-forward)
    "15m": {
        "timeframe": "m15",
        "bars_per_hour": 4,
        "forecast_bars": 4,  # L1 4-bar multi-step (1 hour ahead)
        "min_training_bars": 60,  # Fetcher adds +1 for return-based models (Kalman: 61 OHLC -> 60 returns)
        "indicator_scale": 0.25,  # Scale down indicator periods
        "use_advanced_ensemble": False,  # Keep basic for speed
        "use_walk_forward": False,  # Too short for walk-forward validation
        "horizon_days": 0.0417,  # 4 * 15m / 86400 (time_scale_days for synthesizer)
        "kalman_weight": 0.15,  # Blend weight for StateSpaceKalmanForecaster (0 disables)
    },
    "1h": {
        "timeframe": "h1",
        "bars_per_hour": 1,
        "forecast_bars": 1,  # 1 bar ahead = 1 hour
        "min_training_bars": 60,  # ~1.5 trading weeks (reduced from 100)
        "indicator_scale": 0.5,
        "use_advanced_ensemble": False,  # Keep basic for speed
        "use_walk_forward": False,  # Too short for walk-forward validation
        "horizon_days": 0.0417,  # 1 * 1h / 86400
        "kalman_weight": 0.15,  # Blend weight for StateSpaceKalmanForecaster (0 disables)
    },
    # Medium-term horizons with walk-forward validation (prevents overfitting)
    "4h": {
        "timeframe": "h4",
        "bars_per_hour": 0.25,
        "forecast_bars": 1,  # 1 bar ahead = 4 hours
        "min_training_bars": 100,  # ~17 days (6 bars/day)
        "indicator_scale": 1.0,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "use_walk_forward": True,  # Enable walk-forward validation
        "horizon_days": 0.167,  # 4/24 hours
    },
    "8h": {
        "timeframe": "h8",
        "bars_per_hour": 0.125,
        "forecast_bars": 1,  # 1 bar ahead = 8 hours
        "min_training_bars": 120,  # ~40 days (3 bars/day)
        "indicator_scale": 1.5,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "use_walk_forward": True,  # Enable walk-forward validation
        "horizon_days": 0.333,  # 8/24 hours
    },
    "1D": {
        "timeframe": "d1",
        "bars_per_hour": 1 / 24,
        "forecast_bars": 1,  # 1 bar ahead = 1 day
        "min_training_bars": 200,  # ~10 months (reduced from 500)
        "indicator_scale": 2.0,
        "use_advanced_ensemble": True,  # Use advanced ensemble
        "use_walk_forward": True,  # Enable walk-forward validation
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


def compute_time_scale_days(timeframe: str, forecast_bars: int) -> float:
    """Real time in days for volatility scaling (synthesizer)."""
    return forecast_bars * timeframe_interval_seconds(timeframe) / 86400.0


def _blend_xgb_into_ensemble_pred(
    ensemble_pred: Dict,
    p: float,
    w: float,
) -> None:
    """
    Blend XGBoost P(bullish) into ensemble_pred probabilities; update label, confidence, agreement.

    Treats XGBoost as an extra direction model. Mutates ensemble_pred in place.
    - P_blend[k] = (1-w)*E[k] + w*X[k] with X = {bullish: p, bearish: 1-p, neutral: 0}, then renormalize.
    - label = argmax(P_blend), confidence = P_blend[label].
    - agreement_new = (agreement_old * n_models_base + (1 if xgb agrees else 0)) / (n_models_base + 1).
    - Stores xgb_prob, component_predictions["xgb"], weights["xgb"], n_models.
    """
    E = ensemble_pred.get("probabilities") or {}
    for k in ("bullish", "neutral", "bearish"):
        E[k] = float(E.get(k, 0.0))
    X = {"bullish": p, "bearish": 1.0 - p, "neutral": 0.0}
    P_blend = {
        k: (1.0 - w) * E[k] + w * X[k]
        for k in ("bullish", "neutral", "bearish")
    }
    total = sum(P_blend.values())
    if total <= 0:
        return
    for k in P_blend:
        P_blend[k] /= total
    label_key = max(P_blend, key=P_blend.get)
    label = label_key.capitalize()
    confidence = P_blend[label_key]

    n_models_base = int(ensemble_pred.get("n_models", 2))
    agreement_old = float(ensemble_pred.get("agreement", 0.0))
    xgb_label = "Bullish" if p >= 0.5 else "Bearish"
    xgb_agrees = 1.0 if xgb_label.lower() == label.lower() else 0.0
    agreement_new = (agreement_old * n_models_base + xgb_agrees) / (n_models_base + 1)

    ensemble_pred["xgb_prob"] = p
    comp = ensemble_pred.setdefault("component_predictions", {})
    comp["xgb"] = {
        "label": xgb_label,
        "confidence": float(max(p, 1.0 - p)),
    }
    weights_dict = ensemble_pred.setdefault("weights", {})
    weights_dict["xgb"] = w

    ensemble_pred["label"] = label
    ensemble_pred["confidence"] = confidence
    ensemble_pred["probabilities"] = P_blend
    ensemble_pred["agreement"] = agreement_new
    ensemble_pred["n_models"] = n_models_base + 1


def _blend_kalman_into_ensemble_pred(
    ensemble_pred: Dict,
    kalman_pred: dict,
    w: float,
) -> None:
    """Blend Kalman/SARIMAX directional probabilities into ensemble_pred.

    kalman_pred is expected to contain:
    - label: bullish|neutral|bearish
    - confidence: float
    - probabilities: dict(bullish, neutral, bearish)

    This mirrors the XGB blending pattern but uses a full 3-class distribution.
    """
    if not kalman_pred:
        return

    Kp = (kalman_pred.get("probabilities") or {}).copy()
    if not Kp:
        # Fallback to 2-class mapping if only a label is provided
        k_label = str(kalman_pred.get("label", "neutral")).lower()
        if k_label == "bullish":
            Kp = {"bullish": 0.70, "neutral": 0.20, "bearish": 0.10}
        elif k_label == "bearish":
            Kp = {"bullish": 0.10, "neutral": 0.20, "bearish": 0.70}
        else:
            Kp = {"bullish": 0.20, "neutral": 0.60, "bearish": 0.20}

    E = ensemble_pred.get("probabilities") or {}
    for k in ("bullish", "neutral", "bearish"):
        E[k] = float(E.get(k, 0.0))
        Kp[k] = float(Kp.get(k, 0.0))

    P_blend = {k: (1.0 - w) * E[k] + w * Kp[k] for k in ("bullish", "neutral", "bearish")}
    total = sum(P_blend.values())
    if total <= 0:
        return
    for k in P_blend:
        P_blend[k] /= total

    label_key = max(P_blend, key=P_blend.get)
    label = label_key.capitalize()
    confidence = P_blend[label_key]

    n_models_base = int(ensemble_pred.get("n_models", 2))
    agreement_old = float(ensemble_pred.get("agreement", 0.0))

    kalman_label = str(kalman_pred.get("label", "neutral")).lower()
    kalman_label = "neutral" if kalman_label not in ("bullish", "bearish", "neutral") else kalman_label
    kalman_agrees = 1.0 if kalman_label == label_key else 0.0
    agreement_new = (agreement_old * n_models_base + kalman_agrees) / (n_models_base + 1)

    comp = ensemble_pred.setdefault("component_predictions", {})
    comp["kalman"] = {
        "label": kalman_label.capitalize(),
        "confidence": float(kalman_pred.get("confidence", 0.0) or 0.0),
    }
    weights_dict = ensemble_pred.setdefault("weights", {})
    weights_dict["kalman"] = float(w)

    ensemble_pred["label"] = label
    ensemble_pred["confidence"] = confidence
    ensemble_pred["probabilities"] = P_blend
    ensemble_pred["agreement"] = agreement_new
    ensemble_pred["n_models"] = n_models_base + 1


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


def canonicalize_intraday_points(
    points: list[dict],
    timeframe: str,
) -> list[dict]:
    """Convert raw points to canonical ForecastPoint shape for ml_forecasts_intraday.points.

    Ensures ts is ISO 8601 UTC string (not unix int); when ts is already a string, parses
    and re-emits YYYY-MM-DDTHH:MM:SSZ so storage is always normalized. Adds timeframe and
    1-based step (future step index: step 1 = first future bar). Timeframe must be API/DB
    token: m15, h1, h4 (no 4h_trading in production writer).
    """
    if not points:
        return []
    result = []
    for i, p in enumerate(points):
        ts_raw = p.get("ts")
        if isinstance(ts_raw, (int, float)):
            dt = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
            ts_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(ts_raw, str) and ts_raw.strip():
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                ts_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError):
                ts_iso = ts_raw
        else:
            ts_iso = ""
        result.append({
            "ts": ts_iso,
            "value": p["value"],
            "lower": p["lower"],
            "upper": p["upper"],
            "timeframe": timeframe,
            "step": i + 1,
        })
    return result


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


def validate_ensemble_with_walk_forward(
    df: pd.DataFrame,
    symbol: str,
    horizon: str,
    ensemble,
) -> Dict:
    """
    Validate ensemble using walk-forward optimization.

    Detects overfitting via divergence (val_rmse vs test_rmse).
    If divergence > 20%, returns signal to simplify ensemble.

    Args:
        df: Historical OHLC data
        symbol: Stock ticker
        horizon: Forecast horizon ('4h', '8h', '1D')
        ensemble: Ensemble forecaster to validate

    Returns:
        Dict with 'overfitting_detected' bool and 'divergence' float
    """
    try:
        from src.training.walk_forward_optimizer import WalkForwardOptimizer

        logger.info(
            "Running walk-forward validation for %s %s (divergence threshold=20%%)",
            symbol,
            horizon,
        )

        # Initialize walk-forward optimizer
        wf_optimizer = WalkForwardOptimizer(
            train_days=1000,
            val_days=250,
            test_days=250,
            divergence_threshold=0.20,
        )

        # Prepare data (ensure it has 'actual' column for RMSE)
        val_df = df.copy()
        if "actual" not in val_df.columns:
            # Use close as proxy for actual
            val_df["actual"] = val_df["close"]

        # Create windows
        windows = wf_optimizer.create_windows(val_df)

        if not windows:
            logger.warning("No walk-forward windows created for %s", symbol)
            return {"overfitting_detected": False, "divergence": 0.0}

        # Optimize on most recent window only
        latest_window = windows[-1]
        logger.debug("Using most recent window: %s", latest_window)

        result = wf_optimizer.optimize_window(
            latest_window,
            val_df,
            ensemble,
            param_grid=None,
        )

        # Check divergence
        overfitting_detected = result.divergence > 0.20
        if overfitting_detected:
            logger.warning(
                "%s %s: Divergence %.2f%% > 20%% threshold. "
                "Ensemble simplification recommended.",
                symbol,
                horizon,
                result.divergence * 100,
            )
        else:
            logger.info(
                "%s %s: Divergence %.2f%% within normal range.",
                symbol,
                horizon,
                result.divergence * 100,
            )

        # Get summary
        summary = wf_optimizer.get_divergence_summary()
        logger.info("Walk-forward summary: %s", summary)

        # LOG METRICS TO DATABASE (Phase 7.1 Monitoring)
        try:
            # Create divergence monitor with Supabase client
            divergence_monitor = DivergenceMonitor(
                db_client=None,  # Will log via direct Supabase call below
                divergence_threshold=0.20,
            )

            # Prepare data for logging
            symbol_id = f"symbol_{symbol.lower()}"  # Simple symbol_id generation

            # Log to database using Supabase directly
            metric_record = {
                "symbol_id": symbol_id,
                "symbol": symbol,
                "horizon": horizon,
                "validation_date": datetime.now(timezone.utc).isoformat(),
                "window_id": getattr(result, 'window_id', 0),
                "train_rmse": getattr(result, 'train_rmse', None),
                "val_rmse": result.val_rmse,
                "test_rmse": result.test_rmse,
                "divergence": result.divergence,
                "divergence_threshold": 0.20,
                "is_overfitting": overfitting_detected,
                "model_count": 2,  # 2-model ensemble
                "models_used": ["LSTM", "ARIMA_GARCH"],
                "n_train_samples": getattr(result, 'n_train_samples', len(df) * 0.6),
                "n_val_samples": getattr(result, 'n_val_samples', len(df) * 0.2),
                "n_test_samples": getattr(result, 'n_test_samples', len(df) * 0.2),
                "data_span_days": getattr(result, 'data_span_days', len(df) // 252),
            }

            # Insert into ensemble_validation_metrics table
            db.client.table("ensemble_validation_metrics").insert(metric_record).execute()

            logger.info(
                "Logged metrics to ensemble_validation_metrics: "
                "%s %s divergence=%.2f%% (val_rmse=%.4f, test_rmse=%.4f)",
                symbol,
                horizon,
                result.divergence * 100,
                result.val_rmse,
                result.test_rmse,
            )
        except Exception as log_err:
            logger.warning(
                "Failed to log metrics to database for %s %s: %s",
                symbol,
                horizon,
                log_err,
            )

        return {
            "overfitting_detected": overfitting_detected,
            "divergence": result.divergence,
            "val_rmse": result.val_rmse,
            "test_rmse": result.test_rmse,
            "summary": summary,
        }

    except Exception as e:
        logger.warning(
            "Walk-forward validation failed for %s %s: %s",
            symbol,
            horizon,
            e,
        )
        # Don't fail the entire forecast, just log warning
        return {"overfitting_detected": False, "divergence": 0.0}


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
    # Return-based models (Kalman) need len(returns)>=min_bars; returns=pct_change().dropna() -> len(df)-1
    fetch_limit = min_bars + 1 if config.get("kalman_weight", 0) else min_bars

    # Baseline uses start_idx and end_idx=len(df)-lookahead; need len(X)>=min_bars -> len(df)>=start+lookahead+min_bars
    lookahead_bars = int(config.get("forecast_bars", 1))
    baseline_required_ohlc = BASELINE_START_IDX + min_bars + lookahead_bars + 10  # buffer for NaNs
    fetch_limit = max(fetch_limit, baseline_required_ohlc)

    logger.info("Processing %s intraday forecast for %s", horizon, symbol)
    logger.info("%s %s: fetch_limit=%d (min_bars=%d, lookahead=%d)", symbol, timeframe, fetch_limit, min_bars, lookahead_bars)

    try:
        # Fetch intraday bars
        df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=fetch_limit)
        n_ohlc = len(df)
        n_returns = len(df["close"].pct_change().dropna()) if n_ohlc > 0 and "close" in df.columns else 0
        logger.info(
            "%s %s: OHLC rows=%d, post-pct_change returns=%d (min_bars=%d)",
            symbol,
            timeframe,
            n_ohlc,
            n_returns,
            min_bars,
        )
        logger.info("%s %s: df.columns=%s", symbol, timeframe, list(df.columns))

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

        # SuperTrend (Adaptive vs legacy)
        st_info_raw = None
        adaptive_signal = None
        if getattr(settings, "enable_adaptive_supertrend", False):
            adapter = get_adaptive_supertrend_adapter(
                metric_objective=getattr(settings, "adaptive_st_metric_objective", "sharpe"),
                cache_enabled=getattr(settings, "adaptive_st_caching", True),
                cache_ttl_hours=getattr(settings, "adaptive_st_cache_ttl_hours", 24),
                min_bars=getattr(settings, "adaptive_st_min_bars", 60),
                enable_optimization=getattr(settings, "adaptive_st_optimization", True),
            )
            adaptive_signal = adapter.compute_signal(symbol, df, timeframe)
            if adaptive_signal:
                st_info_raw = {
                    "current_trend": "BULL" if adaptive_signal["trend"] == 1 else "BEAR",
                    "signal_strength": adaptive_signal["signal_strength"],
                    "performance_index": adaptive_signal["performance_index"],
                    "atr": adaptive_signal["distance_pct"] * current_price,
                }
        if st_info_raw is None:
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
                if adaptive_signal and idx == -1:
                    record["supertrend_value"] = adaptive_signal["supertrend_value"]
                    record["supertrend_trend"] = 1 if adaptive_signal["trend"] == 1 else 0
                    record["supertrend_factor"] = adaptive_signal["factor"]
                    record["supertrend_performance_index"] = adaptive_signal["performance_index"]
                    record["supertrend_signal_strength"] = adaptive_signal["signal_strength"]
                    record["signal_confidence"] = int(round(adaptive_signal["confidence"] * 10))
                    record["supertrend_confidence_norm"] = adaptive_signal["confidence"]
                    record["supertrend_distance_norm"] = adaptive_signal["distance_pct"]
                    record["supertrend_distance_pct"] = adaptive_signal["distance_pct"]
                    record["supertrend_metrics"] = adaptive_signal["metrics"]
                elif "supertrend" in df.columns:
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
        forecast_bars = int(config.get("forecast_bars", 1))
        lookahead_bars = forecast_bars  # Baseline uses bar-count for labeling
        time_scale_days = config.get("horizon_days")
        if time_scale_days is None:
            time_scale_days = compute_time_scale_days(timeframe, forecast_bars)

        # Get layer weights (feedback-based for 4h/8h/1D, defaults for 15m/1h)
        weights, weight_source = get_weight_source_for_intraday(
            symbol=symbol,
            symbol_id=symbol_id,
            horizon=horizon,
            use_feedback=use_advanced,
        )

        # Prepare training data (baseline expects bar-count as horizon_days)
        baseline = BaselineForecaster()
        try:
            X, y = baseline.prepare_training_data(df, horizon_days=float(lookahead_bars))
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
                        # ADVANCED ENSEMBLE: 2-3 model ensemble with OHLC data
                        ensemble = get_production_ensemble(
                            horizon=horizon,
                            symbol_id=symbol_id,
                        )

                        # NEW: Walk-forward validation for overfitting detection
                        use_walk_forward = config.get("use_walk_forward", False)
                        if use_walk_forward and len(df) >= 2000:  # Need enough data for WF
                            wf_result = validate_ensemble_with_walk_forward(
                                df=df,
                                symbol=symbol,
                                horizon=horizon,
                                ensemble=ensemble,
                            )
                            # If high divergence detected, simplify ensemble
                            if wf_result.get("overfitting_detected", False):
                                logger.warning(
                                    "%s %s: Simplifying ensemble due to overfitting "
                                    "(divergence=%.2f%%)",
                                    symbol,
                                    horizon,
                                    wf_result.get("divergence", 0) * 100,
                                )
                                # Recreate ensemble with 2-model core only
                                old_model_count = os.environ.get("ENSEMBLE_MODEL_COUNT", "2")
                                os.environ["ENSEMBLE_MODEL_COUNT"] = "2"
                                ensemble = get_production_ensemble(
                                    horizon=horizon,
                                    symbol_id=symbol_id,
                                )
                                os.environ["ENSEMBLE_MODEL_COUNT"] = old_model_count

                        # Align OHLC data with features (pattern from unified_forecast_job.py)
                        min_offset = 50 if len(df) >= 100 else (26 if len(df) >= 60 else 14)
                        start_idx = max(min_offset, 14)
                        end_idx = len(df) - max(1, lookahead_bars)
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

                        # XGBoost blend: extra direction model contributing P(bullish) into probabilities.
                        # Require min samples per class to avoid silent bearish bias (neutral→bearish).
                        xgb_weight = config.get("xgb_weight", 0.2)
                        min_xgb_per_class = config.get("min_xgb_samples_per_class", 5)
                        if 0 < xgb_weight < 1 and min_xgb_per_class >= 1:
                            try:
                                y_binary = y.map(
                                    lambda v: "bullish"
                                    if str(v).lower() == "bullish"
                                    else "bearish"
                                )
                                n_bull = int((y_binary == "bullish").sum())
                                n_bear = int((y_binary == "bearish").sum())
                                if (
                                    n_bull >= min_xgb_per_class
                                    and n_bear >= min_xgb_per_class
                                    and len(X) >= min_bars
                                ):
                                    xgb_forecaster = XGBoostForecaster()
                                    xgb_forecaster.train(X, y_binary, min_samples=min_bars)
                                    proba = xgb_forecaster.predict_proba(last_features)
                                    if proba is not None and len(proba) > 0:
                                        p = float(proba[0])
                                        _blend_xgb_into_ensemble_pred(
                                            ensemble_pred, p, xgb_weight
                                        )
                                        logger.debug(
                                            "%s %s: XGB blend p=%.3f w=%.2f -> %s (%.0f%%)",
                                            symbol,
                                            horizon,
                                            p,
                                            xgb_weight,
                                            ensemble_pred.get("label"),
                                            ensemble_pred.get("confidence", 0) * 100,
                                        )
                            except Exception as xgb_e:
                                logger.debug(
                                    "XGBoost blend skipped for %s %s: %s",
                                    symbol,
                                    horizon,
                                    xgb_e,
                                )

                except Exception as e:
                    logger.warning("Ensemble training failed for %s: %s", symbol, e, exc_info=True)
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

        # Kalman/SARIMAX blend (15m/1h only, before synthesizer so blend affects forecast)
        kalman_debug = None
        try:
            kalman_weight = float(config.get("kalman_weight", 0.0) or 0.0)
        except Exception:
            kalman_weight = 0.0
        enable_kalman = os.environ.get("ENABLE_KALMAN_INTRADAY", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
        if ensemble_pred and 0.0 < kalman_weight < 1.0 and enable_kalman:
            try:
                if "garch_vol_regime" in df.columns and df["garch_vol_regime"].notna().any():
                    df["_kalman_vol_regime"] = df["garch_vol_regime"].astype(float)
                elif "atr_normalized" in df.columns and df["atr_normalized"].notna().any():
                    _atr = df["atr_normalized"].astype(float)
                    p33 = float(_atr.dropna().quantile(0.33))
                    p67 = float(_atr.dropna().quantile(0.67))
                    regime = pd.Series(1.0, index=df.index)
                    regime[_atr < p33] = 0.0
                    regime[_atr > p67] = 2.0
                    df["_kalman_vol_regime"] = regime
                else:
                    df["_kalman_vol_regime"] = 1.0

                exog_cols = ["kdj_j_divergence", "supertrend_trend", "_kalman_vol_regime"]
                # Kalman needs len(returns)>=min_bars; returns=pct_change().dropna() -> len(df)-1
                # Fetcher already requests min_bars+1 when kalman_weight>0, so len(df)>=min_bars+1
                kalman_min_bars = min_bars  # min_bars = required returns count
                if all(c in df.columns for c in exog_cols) and len(df) >= fetch_limit:
                    kalman = StateSpaceKalmanForecaster(
                        horizon=horizon,
                        arima_order=(1, 0, 1),
                        bullish_threshold=0.002,
                        bearish_threshold=-0.002,
                        min_bars=kalman_min_bars,
                    )
                    kalman.train(df, exog_cols=exog_cols)
                    kalman_pred = kalman.predict(df.tail(1), exog_cols=exog_cols)

                    if kalman_pred:
                        health = kalman_pred.get("kalman_health") or {}
                        converged = bool(health.get("converged", False))
                        exog_missing_rate = float(health.get("exog_missing_rate", 0.0))
                        exog_ok = exog_missing_rate <= 0.20  # heavy ffill/bfill = stale exog
                        effective_weight = kalman_weight if (converged and exog_ok) else 0.0
                        if effective_weight > 0:
                            _blend_kalman_into_ensemble_pred(ensemble_pred, kalman_pred, effective_weight)
                        kalman_debug = {
                            "drift": kalman_pred.get("kalman_drift"),
                            "forecast_return": kalman_pred.get("forecast_return"),
                            "exog_coeffs": kalman_pred.get("kalman_exog_coeffs"),
                            "label": kalman_pred.get("label"),
                            "confidence": kalman_pred.get("confidence"),
                            "health": kalman_pred.get("kalman_health"),
                        }
                        if not converged:
                            logger.debug(
                                "%s %s: Kalman fit not converged, blend disabled (w=0)",
                                symbol,
                                horizon,
                            )
                        elif not exog_ok:
                            logger.debug(
                                "%s %s: Kalman exog_missing_rate=%.2f > 0.20, blend disabled (w=0)",
                                symbol,
                                horizon,
                                exog_missing_rate,
                            )
                        else:
                            logger.debug(
                                "%s %s: Kalman blend w=%.2f -> %s (%.0f%%)",
                                symbol,
                                horizon,
                                effective_weight,
                                ensemble_pred.get("label"),
                                ensemble_pred.get("confidence", 0) * 100,
                            )
            except Exception as e:
                logger.warning("Kalman/SARIMAX component failed for %s %s: %s", symbol, horizon, e)

        # Option B: recent residuals as features for next inference (horizon+1 without retraining)
        recent_residuals = db.get_recent_intraday_residuals(symbol_id, horizon, limit=20)

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
            horizon_days=time_scale_days,  # Real time in days for sqrt scaling
            timeframe=timeframe,
            recent_residuals=recent_residuals,
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
        # 15m multi-step: use forecast_bars so stored points = 4 future bars at 15-min intervals
        if horizon == "15m":
            short_steps = int(config.get("forecast_bars", 8))
        else:
            short_steps = int(short_steps_by_horizon.get(horizon, 8))
        # 15m 4-bar: each step = one bar (15 min); others: subdivide horizon
        if horizon == "15m" and short_steps == 4:
            short_interval_sec = horizon_seconds  # 15 min per step
        else:
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
            "recent_residuals": recent_residuals,
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

        # Save intraday forecast (single-target); canonicalize points for storage (ISO ts, timeframe, step).
        # Storage contract: step 1 = first future bar. build_intraday_short_points emits anchor at i=0 then
        # future points; slice off the anchor so we only persist future steps (step 1, 2, ...).
        short_points_future = short_points[1:] if len(short_points) > 1 else []

        # Store synthesis details for auditing/debug.
        if ensemble_pred:
            synthesis_data = {"ensemble_result": ensemble_pred}
            if kalman_debug:
                synthesis_data["kalman"] = kalman_debug
        else:
            synthesis_data = None

        forecast_id = db.insert_intraday_forecast(
            symbol_id=symbol_id,
            symbol=symbol,
            horizon=horizon,
            timeframe=timeframe,
            overall_label=consensus_direction,
            confidence=adjusted_confidence,
            points=canonicalize_intraday_points(short_points_future, timeframe),
            target_price=synth_result.target,
            current_price=current_price,
            supertrend_component=synth_result.supertrend_component,
            sr_component=synth_result.polynomial_component,
            ensemble_component=synth_result.ml_component,
            supertrend_direction=st_info_raw.get("current_trend", "NEUTRAL"),
            ensemble_label=ensemble_pred.get("label", "neutral"),
            layers_agreeing=synth_result.layers_agreeing,
            expires_at=expires_at.isoformat(),
            synthesis_data=synthesis_data,
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
                    # Option B: enrich with OHLC + recomputed indicators (history + predicted)
                    path_points = attach_indicators_to_forecast_points(path_df, path_points)

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
                        points=canonicalize_intraday_points(path_points, tf),
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


def _log_forecast_verification(horizon: str) -> None:
    """Query ml_forecasts_intraday for recently created forecasts and log counts by symbol."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        resp = (
            db.client.table("ml_forecasts_intraday")
            .select("symbol")
            .eq("horizon", horizon)
            .gte("created_at", cutoff)
            .execute()
        )
        rows = resp.data or []
        from collections import Counter

        counts = Counter(r.get("symbol", "") for r in rows if r.get("symbol"))
        if counts:
            logger.info(
                "Post-write verification: %d forecasts in last 15m for %s (by symbol: %s)",
                len(rows),
                horizon,
                dict(counts),
            )
        else:
            logger.warning("Post-write verification: no ml_forecasts_intraday rows in last 15m for %s", horizon)
    except Exception as e:
        logger.debug("Forecast verification query failed: %s", e)


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
        try:
            if process_symbol_intraday(symbol, args.horizon, generate_paths=args.generate_paths):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            fail_count += 1
            logger.error("Per-symbol exception for %s: %s", symbol, e, exc_info=True)

    # Post-write verification: verify forecasts were written
    _log_forecast_verification(args.horizon)

    logger.info("=" * 60)
    logger.info("Intraday Forecast Job Complete")
    logger.info("Success: %d, Failed: %d", success_count, fail_count)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
