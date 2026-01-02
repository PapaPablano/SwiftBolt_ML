"""Main ML forecasting job that generates predictions for all symbols."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.data.data_validator import OHLCValidator  # noqa: E402
from src.features.technical_indicators import (  # noqa: E402
    add_technical_features,
)
from src.features.support_resistance_detector import (  # noqa: E402
    SupportResistanceDetector,
)
from src.backtesting.walk_forward_tester import (  # noqa: E402
    WalkForwardBacktester,
)
from src.monitoring.forecast_quality import (  # noqa: E402
    ForecastQualityMonitor,
)
from src.monitoring.confidence_calibrator import (  # noqa: E402
    ConfidenceCalibrator,
)
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402
from src.forecast_synthesizer import (  # noqa: E402
    ForecastSynthesizer,
    ForecastResult,
)
from src.forecast_weights import get_default_weights  # noqa: E402


# Global calibrator instance (loaded once, reused across symbols)
_calibrator: ConfidenceCalibrator | None = None


def get_calibrator() -> ConfidenceCalibrator:
    """Get or create the global confidence calibrator."""
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
        # Try to load historical data for calibration
        try:
            historical = db.fetch_historical_forecasts_for_calibration(
                lookback_days=90, min_samples=100
            )
            if historical is not None and len(historical) >= 100:
                _calibrator.fit(historical)
                logger.info(
                    f"Confidence calibrator fitted with {len(historical)} samples"
                )
            else:
                logger.info(
                    "Insufficient historical data for calibration, using raw confidence"
                )
        except Exception as e:
            logger.warning(f"Could not load calibration data: {e}")
    return _calibrator

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def convert_sr_to_synthesizer_format(sr_levels: dict, current_price: float) -> dict:
    """
    Convert SupportResistanceDetector output to format expected by ForecastSynthesizer.

    The detector uses snake_case Python naming, while the synthesizer uses
    camelCase (matching the Edge Function API format).

    Args:
        sr_levels: Output from SupportResistanceDetector.find_all_levels()
        current_price: Current price for fallback values

    Returns:
        Dict in synthesizer-expected format
    """
    indicators = sr_levels.get("indicators", {})

    # Convert polynomial indicator
    poly_in = indicators.get("polynomial", {})
    polynomial = {
        "support": poly_in.get("current_support", current_price * 0.95),
        "resistance": poly_in.get("current_resistance", current_price * 1.05),
        "supportSlope": poly_in.get("support_slope", 0),
        "resistanceSlope": poly_in.get("resistance_slope", 0),
        "supportTrend": _slope_to_trend(poly_in.get("support_slope", 0)),
        "resistanceTrend": _slope_to_trend(poly_in.get("resistance_slope", 0)),
        "forecastSupport": poly_in.get("forecast_support", []),
        "forecastResistance": poly_in.get("forecast_resistance", []),
        "isDiverging": poly_in.get("is_diverging", False),
        "isConverging": poly_in.get("is_converging", False),
    }

    # Convert logistic indicator
    logistic_in = indicators.get("logistic", {})
    logistic = {
        "supportLevels": [
            {
                "level": lvl.get("level", 0),
                "probability": lvl.get("probability", 0.5),
            }
            for lvl in logistic_in.get("support_levels", [])
        ],
        "resistanceLevels": [
            {
                "level": lvl.get("level", 0),
                "probability": lvl.get("probability", 0.5),
            }
            for lvl in logistic_in.get("resistance_levels", [])
        ],
        "signals": logistic_in.get("signals", []),
    }

    # Convert pivot levels indicator
    pivot_in = indicators.get("pivot_levels", {})
    pivot_levels_list = pivot_in.get("pivot_levels", [])

    # Build pivotLevels object with period5, period25, period50, period100
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

    # Ensure all standard periods exist
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


def _slope_to_trend(slope: float) -> str:
    """Convert numeric slope to trend label."""
    if slope > 0.0001:
        return "rising"
    elif slope < -0.0001:
        return "falling"
    return "flat"


def convert_supertrend_to_synthesizer_format(st_info: dict) -> dict:
    """
    Ensure SuperTrend info is in the format expected by ForecastSynthesizer.

    Args:
        st_info: Output from SuperTrendAI.calculate()[1]

    Returns:
        Dict with current_trend, signal_strength, performance_index
    """
    return {
        "current_trend": st_info.get("current_trend", "NEUTRAL"),
        "signal_strength": st_info.get("signal_strength", 5),
        "performance_index": st_info.get("performance_index", 0.5),
        "atr": st_info.get("atr"),  # Optional, synthesizer will calculate if missing
    }


def forecast_result_to_points(
    result: ForecastResult,
    start_ts: datetime,
    horizon_days: int,
) -> list:
    """
    Convert ForecastResult to forecast points format for database storage.

    Args:
        result: ForecastResult from synthesizer
        start_ts: Starting timestamp
        horizon_days: Number of days in forecast horizon

    Returns:
        List of forecast point dicts
    """
    from datetime import timedelta

    points = []
    for i in range(1, horizon_days + 1):
        # Interpolate target from current to final
        progress = i / horizon_days
        if result.direction == "BULLISH":
            # Gradual move toward target
            value = result.lower_band + (result.target - result.lower_band) * progress
        elif result.direction == "BEARISH":
            # Gradual move toward target
            value = result.upper_band - (result.upper_band - result.target) * progress
        else:
            value = (result.lower_band + result.upper_band) / 2

        # For final day, use actual target
        if i == horizon_days:
            value = result.target

        points.append({
            "ts": (start_ts + timedelta(days=i)).isoformat(),
            "value": round(value, 2),
            "lower": round(result.lower_band, 2),
            "upper": round(result.upper_band, 2),
        })

    return points


def apply_sr_constraints(
    forecast: dict,
    sr_levels: dict,
    current_price: float,
    sr_probabilities: dict | None = None,
) -> dict:
    """
    Apply S/R constraints to forecast points and adjust confidence.

    Uses the new 3-indicator S/R system:
    - Pivot Levels (multi-timeframe)
    - Polynomial Regression (dynamic S/R with slopes)
    - Logistic Regression (ML-based with probabilities)

    Args:
        forecast: Forecast dict with label, confidence, points
        sr_levels: S/R levels from detector (new format with indicators key)
        current_price: Current closing price
        sr_probabilities: Optional dict with support_hold_probability and
                          resistance_hold_probability (can be extracted from logistic)

    Returns:
        Updated forecast with S/R constraints applied
    """
    forecast = forecast.copy()
    label = forecast["label"]
    points = forecast.get("points", [])

    # Extract hold probabilities from logistic indicator if available
    # This is the new approach using ML-based probability predictions
    indicators = sr_levels.get("indicators", {})
    logistic_result = indicators.get("logistic", {})

    # Get probabilities from logistic indicator's nearest levels
    support_levels = logistic_result.get("support_levels", [])
    resistance_levels = logistic_result.get("resistance_levels", [])

    # Calculate hold probability as average of high-probability levels
    # Higher probability = more likely to hold
    logistic_support_prob = 0.5
    logistic_resistance_prob = 0.5

    if support_levels:
        high_prob_supports = [
            lvl["probability"]
            for lvl in support_levels
            if lvl.get("probability", 0) >= 0.7
        ]
        if high_prob_supports:
            logistic_support_prob = (
                sum(high_prob_supports) / len(high_prob_supports)
            )

    if resistance_levels:
        high_prob_resistances = [
            lvl["probability"]
            for lvl in resistance_levels
            if lvl.get("probability", 0) >= 0.7
        ]
        if high_prob_resistances:
            logistic_resistance_prob = (
                sum(high_prob_resistances) / len(high_prob_resistances)
            )

    # Use provided probabilities if available, otherwise use logistic-derived
    probs = sr_probabilities or {}
    support_hold_prob = probs.get(
        "support_hold_probability", logistic_support_prob
    )
    resistance_hold_prob = probs.get(
        "resistance_hold_probability", logistic_resistance_prob
    )

    nearest_support = sr_levels.get("nearest_support")
    nearest_resistance = sr_levels.get("nearest_resistance")
    support_dist_pct = sr_levels.get("support_distance_pct")
    resistance_dist_pct = sr_levels.get("resistance_distance_pct")

    # Don't hard-cap forecast values - ML model predictions should be shown as-is
    # S/R levels are informational; confidence adjustments handle the uncertainty
    # Just ensure bounds are properly ordered (lower < value < upper)
    constrained_points = []
    for point in points:
        value = point["value"]
        lower = point.get("lower", value * 0.97)
        upper = point.get("upper", value * 1.03)

        # Ensure bounds are in correct order
        if lower > value:
            lower = value * 0.97
        if upper < value:
            upper = value * 1.03
        if lower > upper:
            lower, upper = upper, lower

        constrained_points.append({
            **point,
            "value": round(value, 2),
            "lower": round(lower, 2),
            "upper": round(upper, 2),
        })

    forecast["points"] = constrained_points

    # Adjust confidence based on S/R proximity
    original_confidence = forecast["confidence"]
    adjusted_confidence = original_confidence

    # Reduce confidence if predicting bullish near resistance
    # Phase 2 enhancement: scale penalty by resistance hold probability
    if label == "bullish" and resistance_dist_pct is not None:
        if resistance_dist_pct < 2.0:  # Within 2% of resistance
            # Higher hold probability = stronger penalty (resistance more likely to hold)
            hold_factor = 0.5 + 0.5 * resistance_hold_prob  # 0.5 to 1.0
            base_penalty = (2.0 - resistance_dist_pct) / 2.0 * 0.15  # Up to 15% base
            penalty = base_penalty * hold_factor
            adjusted_confidence = max(0.3, original_confidence - penalty)
            logger.debug(
                f"Bullish near resistance ({resistance_dist_pct:.2f}%), "
                f"hold_prob={resistance_hold_prob:.2f}, "
                f"confidence {original_confidence:.2f} -> {adjusted_confidence:.2f}"
            )

    # Reduce confidence if predicting bearish near support
    # Phase 2 enhancement: scale penalty by support hold probability
    elif label == "bearish" and support_dist_pct is not None:
        if support_dist_pct < 2.0:  # Within 2% of support
            # Higher hold probability = stronger penalty (support more likely to hold)
            hold_factor = 0.5 + 0.5 * support_hold_prob  # 0.5 to 1.0
            base_penalty = (2.0 - support_dist_pct) / 2.0 * 0.15  # Up to 15% base
            penalty = base_penalty * hold_factor
            adjusted_confidence = max(0.3, original_confidence - penalty)
            logger.debug(
                f"Bearish near support ({support_dist_pct:.2f}%), "
                f"hold_prob={support_hold_prob:.2f}, "
                f"confidence {original_confidence:.2f} -> {adjusted_confidence:.2f}"
            )

    forecast["confidence"] = adjusted_confidence

    # Add S/R metadata to forecast
    # Include both summary data and full indicator results
    poly_result = indicators.get("polynomial", {})
    pivot_result = indicators.get("pivot_levels", {})

    forecast["sr_levels"] = {
        # Summary levels
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "support_distance_pct": support_dist_pct,
        "resistance_distance_pct": resistance_dist_pct,
        "all_supports": sr_levels.get("all_supports", [])[:5],
        "all_resistances": sr_levels.get("all_resistances", [])[:5],
        # Hold probabilities (from logistic indicator)
        "support_hold_probability": support_hold_prob,
        "resistance_hold_probability": resistance_hold_prob,
        # Polynomial regression data
        "polynomial": {
            "support": poly_result.get("current_support"),
            "resistance": poly_result.get("current_resistance"),
            "support_slope": poly_result.get("support_slope", 0),
            "resistance_slope": poly_result.get("resistance_slope", 0),
        },
        # Multi-timeframe pivot levels
        "pivot_levels": pivot_result.get("pivot_levels", []),
        # Logistic ML levels (top 3 each)
        "logistic_support": support_levels[:3] if support_levels else [],
        "logistic_resistance": resistance_levels[:3] if resistance_levels else [],
        # Signals from all indicators
        "signals": sr_levels.get("signals", []),
    }

    # Calculate S/R density (number of levels within 5% of current price)
    all_levels = sr_levels.get("all_supports", [])[:10] + sr_levels.get("all_resistances", [])[:10]
    levels_within_5pct = [
        level for level in all_levels
        if abs(level - current_price) / current_price <= 0.05
    ]
    forecast["sr_density"] = len(levels_within_5pct)

    return forecast


def process_symbol(symbol: str) -> None:
    """
    Process a single symbol: fetch data, train model, generate forecasts.

    Includes:
    - Data validation and quality checks
    - Baseline ML forecasts for multiple horizons
    - SuperTrend AI indicator with K-means clustering
    - Confidence calibration based on historical accuracy

    Args:
        symbol: Stock ticker symbol
    """
    logger.info(f"Processing {symbol}...")

    try:
        # Fetch most recent bars (returns latest first, sorted ascending)
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)

        if len(df) < settings.min_bars_for_training:
            logger.warning(
                f"Insufficient data for {symbol}: {len(df)} bars "
                f"(need {settings.min_bars_for_training})"
            )
            return

        # === Data Validation (ML Improvement Plan 2.1) ===
        validator = OHLCValidator()
        df, validation_result = validator.validate(df, fix_issues=True)
        data_quality_score = validator.get_data_quality_score(df)

        if not validation_result.is_valid:
            logger.warning(
                f"Data quality issues for {symbol}: {validation_result.issues}"
            )

        # Calculate data quality multiplier for confidence adjustment
        data_quality_multiplier = max(
            0.9, 1.0 - (validation_result.rows_flagged / max(1, len(df)) * 0.2)
        )

        # Calculate sample size multiplier (per ML Improvement Plan 1.1)
        sample_size_multiplier = min(
            1.0, len(df) / settings.min_bars_for_high_confidence
        )

        logger.info(
            f"Data quality for {symbol}: score={data_quality_score:.2f}, "
            f"quality_mult={data_quality_multiplier:.2f}, "
            f"size_mult={sample_size_multiplier:.2f}"
        )

        # Get confidence calibrator
        calibrator = get_calibrator()

        # Add technical indicators (includes S/R features)
        df = add_technical_features(df)

        # Extract S/R levels using new 3-indicator system
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        current_price = df["close"].iloc[-1]

        # Get indicator results for logging
        indicators = sr_levels.get("indicators", {})
        poly_result = indicators.get("polynomial", {})
        logistic_result = indicators.get("logistic", {})

        logger.info(
            f"S/R Levels for {symbol}: support={sr_levels.get('nearest_support')}, "
            f"resistance={sr_levels.get('nearest_resistance')}, price={current_price:.2f}"
        )

        # Log indicator details
        if poly_result:
            s_slope = poly_result.get('support_slope', 0)
            r_slope = poly_result.get('resistance_slope', 0)
            logger.info(
                f"  Polynomial S/R: support={poly_result.get('current_support')}, "
                f"resistance={poly_result.get('current_resistance')}, "
                f"slopes=(S:{s_slope:.4f}, R:{r_slope:.4f})"
            )

        if logistic_result:
            n_support = len(logistic_result.get("support_levels", []))
            n_resistance = len(logistic_result.get("resistance_levels", []))
            logger.info(
                f"  Logistic S/R: {n_support} support levels, "
                f"{n_resistance} resistance levels, "
                f"signals={logistic_result.get('signals', [])}"
            )

        # S/R probabilities extracted directly from logistic in apply_sr_constraints
        sr_probabilities = {}

        # Get symbol_id
        symbol_id = db.get_symbol_id(symbol)

        # === Walk-forward backtest (validation) ===
        backtester = WalkForwardBacktester(
            train_window=252,
            test_window=21,
            step_size=5,
        )
        backtest_metrics = None
        try:
            baseline_bt = BaselineForecaster()
            backtest_metrics = backtester.backtest(
                df,
                baseline_bt,
                horizons=["1D"],
            )
            logger.info(
                "Backtest %s - acc=%.2f%%, sharpe=%.2f, win_rate=%.2f%%",
                symbol,
                backtest_metrics.accuracy * 100,
                backtest_metrics.sharpe_ratio,
                backtest_metrics.win_rate * 100,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Backtest failed for %s: %s", symbol, e)

        # === SuperTrend AI Processing ===
        supertrend_data = None
        st_info_raw = None  # Keep raw st_info for synthesizer
        try:
            supertrend = SuperTrendAI(df)
            st_df, st_info_raw = supertrend.calculate()

            supertrend_data = {
                "supertrend_factor": st_info_raw["target_factor"],
                "supertrend_performance": st_info_raw["performance_index"],
                "supertrend_signal": int(st_df["supertrend_signal"].iloc[-1]),
                "trend_label": st_info_raw["current_trend"],
                "trend_confidence": st_info_raw["signal_strength"],
                "stop_level": float(st_df["supertrend"].iloc[-1]),
                "trend_duration_bars": st_info_raw["trend_duration_bars"],
            }

            logger.info(
                f"SuperTrend AI for {symbol}: "
                f"factor={st_info_raw['target_factor']:.2f}, "
                f"trend={st_info_raw['current_trend']}, "
                f"confidence={st_info_raw['signal_strength']}/10"
            )

            # Store signals in supertrend_signals table if any new signals
            if st_info_raw["signals"]:
                db.upsert_supertrend_signals(symbol, st_info_raw["signals"])

        except Exception as e:
            logger.warning(f"SuperTrend AI failed for {symbol}: {e}")
            # Create fallback st_info for synthesizer
            st_info_raw = {
                "current_trend": "NEUTRAL",
                "signal_strength": 5,
                "performance_index": 0.5,
                "atr": current_price * 0.02,
            }

        # === Initialize Forecast Synthesizer ===
        synthesizer = ForecastSynthesizer(weights=get_default_weights())
        sr_response = convert_sr_to_synthesizer_format(sr_levels, current_price)
        supertrend_for_synth = convert_supertrend_to_synthesizer_format(st_info_raw)

        # === Generate forecasts for each horizon ===
        for horizon in settings.forecast_horizons:
            logger.info(f"Generating {horizon} forecast for {symbol}")

            # Use ensemble forecaster (RF + GB) for better accuracy
            use_ensemble = getattr(settings, "use_ensemble_forecaster", True)

            if use_ensemble:
                # Prepare data for ensemble
                baseline = BaselineForecaster()
                X, y = baseline.prepare_training_data(
                    df,
                    horizon_days=baseline._parse_horizon(horizon),
                )

                # Create and train ensemble
                forecaster = EnsembleForecaster(
                    horizon=horizon,
                    rf_weight=0.5,
                    gb_weight=0.5,
                )
                forecaster.train(X, y)

                # Generate prediction
                last_features = X.tail(1)
                ensemble_pred = forecaster.predict(last_features)

                # Get ensemble probabilities for directional forecasts
                ensemble_probs = ensemble_pred.get("probabilities", {})

                # === Use 3-Layer Forecast Synthesizer ===
                synth_result = synthesizer.generate_1d_forecast(
                    current_price=current_price,
                    df=df,
                    supertrend_info=supertrend_for_synth,
                    sr_response=sr_response,
                    ensemble_result=ensemble_pred,
                    symbol=symbol,
                )

                # Generate forecast points from synthesizer result
                horizon_days = baseline._parse_horizon(horizon)
                synth_points = forecast_result_to_points(
                    synth_result,
                    df["ts"].iloc[-1],
                    horizon_days,
                )

                forecast = {
                    "label": synth_result.direction.lower(),
                    "confidence": synth_result.confidence,
                    "horizon": horizon,
                    "points": synth_points,
                    "probabilities": ensemble_probs,
                    "rf_prediction": ensemble_pred.get("rf_prediction"),
                    "gb_prediction": ensemble_pred.get("gb_prediction"),
                    "agreement": ensemble_pred.get("agreement"),
                    "ensemble_type": "RF+GB",
                    "backtest": (
                        backtest_metrics.__dict__ if backtest_metrics else None
                    ),
                    "training_stats": forecaster.training_stats,
                    # 3-layer synthesis metadata
                    "synthesis": {
                        "target": synth_result.target,
                        "upper_band": synth_result.upper_band,
                        "lower_band": synth_result.lower_band,
                        "layers_agreeing": synth_result.layers_agreeing,
                        "reasoning": synth_result.reasoning,
                        "key_drivers": synth_result.key_drivers,
                        "supertrend_component": synth_result.supertrend_component,
                        "polynomial_component": synth_result.polynomial_component,
                        "ml_component": synth_result.ml_component,
                    },
                }

                # Apply S/R constraints (adds sr_levels metadata)
                forecast = apply_sr_constraints(
                    forecast, sr_levels, current_price, sr_probabilities
                )

                # === Apply Confidence Calibration (ML Improvement Plan 1.2) ===
                raw_confidence = forecast["confidence"]
                adjusted_confidence = raw_confidence

                # 1. Apply calibration if calibrator is fitted
                if calibrator.is_fitted:
                    adjusted_confidence = calibrator.calibrate(adjusted_confidence)

                # 2. Apply data quality multiplier
                adjusted_confidence *= data_quality_multiplier

                # 3. Apply sample size multiplier
                adjusted_confidence *= sample_size_multiplier

                # Clamp to valid range
                adjusted_confidence = float(np.clip(adjusted_confidence, 0.40, 0.95))

                forecast["confidence"] = adjusted_confidence
                forecast["raw_confidence"] = raw_confidence
                forecast["data_quality"] = {
                    "score": data_quality_score,
                    "quality_multiplier": data_quality_multiplier,
                    "sample_size_multiplier": sample_size_multiplier,
                    "validation_issues": validation_result.issues,
                    "n_training_samples": len(X),
                }

                if adjusted_confidence != raw_confidence:
                    logger.info(
                        f"  Confidence adjusted: {raw_confidence:.2f} -> "
                        f"{adjusted_confidence:.2f}"
                    )
            else:
                # Fallback to baseline forecaster with synthesizer
                baseline_forecaster = BaselineForecaster()
                baseline_forecast = baseline_forecaster.generate_forecast(df, horizon)

                # Create a mock ensemble result from baseline
                mock_ensemble = {
                    "label": baseline_forecast["label"],
                    "confidence": baseline_forecast["confidence"],
                    "agreement": False,
                }

                # Use synthesizer for directional forecast
                synth_result = synthesizer.generate_1d_forecast(
                    current_price=current_price,
                    df=df,
                    supertrend_info=supertrend_for_synth,
                    sr_response=sr_response,
                    ensemble_result=mock_ensemble,
                    symbol=symbol,
                )

                horizon_days = baseline_forecaster._parse_horizon(horizon)
                synth_points = forecast_result_to_points(
                    synth_result,
                    df["ts"].iloc[-1],
                    horizon_days,
                )

                forecast = {
                    "label": synth_result.direction.lower(),
                    "confidence": synth_result.confidence,
                    "horizon": horizon,
                    "points": synth_points,
                    "training_stats": getattr(
                        baseline_forecaster, "training_stats", None
                    ),
                    "synthesis": synth_result.to_dict(),
                }

                # Apply S/R constraints
                forecast = apply_sr_constraints(
                    forecast, sr_levels, current_price, sr_probabilities
                )

                # === Apply Confidence Calibration (fallback path) ===
                raw_confidence = forecast["confidence"]
                adjusted_confidence = raw_confidence

                if calibrator.is_fitted:
                    adjusted_confidence = calibrator.calibrate(adjusted_confidence)

                adjusted_confidence *= data_quality_multiplier
                adjusted_confidence *= sample_size_multiplier

                adjusted_confidence = float(np.clip(adjusted_confidence, 0.40, 0.95))

                forecast["confidence"] = adjusted_confidence
                forecast["raw_confidence"] = raw_confidence
                forecast["data_quality"] = {
                    "score": data_quality_score,
                    "quality_multiplier": data_quality_multiplier,
                    "sample_size_multiplier": sample_size_multiplier,
                    "validation_issues": validation_result.issues,
                    "n_training_samples": len(df) - 50,  # Approximate
                }

            # Quality monitoring (log-only)
            quality_score = ForecastQualityMonitor.compute_quality_score(
                {
                    "confidence": forecast.get("confidence", 0.5),
                    "model_agreement": forecast.get("agreement", 0.75),
                    "created_at": datetime.now(),
                    "conflicting_signals": supertrend_data.get(
                        "conflicting_signals", 0
                    )
                    if supertrend_data
                    else 0,
                }
            )
            issues = ForecastQualityMonitor.check_quality_issues(
                {
                    "confidence": forecast.get("confidence", 0.5),
                    "model_agreement": forecast.get("agreement", 0.75),
                    "created_at": datetime.now(),
                    "conflicting_signals": (
                        supertrend_data.get("conflicting_signals", 0)
                        if supertrend_data
                        else 0
                    ),
                }
            )

            # Save to database (include SuperTrend, S/R, and synthesis data)
            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=forecast["horizon"],
                overall_label=forecast["label"],
                confidence=forecast["confidence"],
                points=forecast["points"],
                supertrend_data=supertrend_data,
                backtest_metrics=forecast.get("backtest"),
                quality_score=quality_score,
                quality_issues=issues,
                model_agreement=forecast.get("agreement"),
                training_stats=forecast.get("training_stats"),
                sr_levels=forecast.get("sr_levels"),
                sr_density=forecast.get("sr_density"),
                synthesis_data=forecast.get("synthesis"),
            )

            # Log synthesis results
            synth_info = forecast.get("synthesis", {})
            logger.info(
                f"Saved {horizon} forecast for {symbol}: "
                f"{forecast['label'].upper()} target=${synth_info.get('target', 0):.2f} "
                f"({forecast['confidence']:.0%} conf, "
                f"{synth_info.get('layers_agreeing', 0)}/3 layers)"
            )
            if use_ensemble:
                logger.info(
                    f"  Ensemble: RF={forecast.get('rf_prediction')}, "
                    f"GB={forecast.get('gb_prediction')}, "
                    f"agreement={forecast.get('agreement')}"
                )
            logger.info(
                f"  Bands: ${synth_info.get('lower_band', 0):.2f} - "
                f"${synth_info.get('upper_band', 0):.2f} | "
                f"Drivers: {synth_info.get('key_drivers', [])[:2]}"
            )
            logger.debug(
                "Quality score %.3f, issues=%s",
                quality_score,
                issues,
            )

    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}", exc_info=True)


def main() -> None:
    """Main forecasting job entry point."""
    logger.info("=" * 80)
    logger.info("Starting ML Forecasting Job")
    logger.info(f"Processing {len(settings.symbols_to_process)} symbols")
    logger.info(f"Horizons: {settings.forecast_horizons}")
    logger.info("=" * 80)

    symbols_processed = 0
    symbols_failed = 0

    for symbol in settings.symbols_to_process:
        try:
            process_symbol(symbol)
            symbols_processed += 1
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            symbols_failed += 1

    logger.info("=" * 80)
    logger.info("ML Forecasting Job Complete")
    logger.info(f"Processed: {symbols_processed}")
    logger.info(f"Failed: {symbols_failed}")
    logger.info("=" * 80)

    # Close database connections
    db.close()


if __name__ == "__main__":
    main()
