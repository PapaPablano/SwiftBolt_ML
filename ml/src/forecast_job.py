"""Main ML forecasting job that generates predictions for all symbols."""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
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
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def apply_sr_constraints(
    forecast: dict,
    sr_levels: dict,
    current_price: float,
) -> dict:
    """
    Apply S/R constraints to forecast points and adjust confidence.

    Args:
        forecast: Forecast dict with label, confidence, points
        sr_levels: S/R levels from detector
        current_price: Current closing price

    Returns:
        Updated forecast with S/R constraints applied
    """
    forecast = forecast.copy()
    label = forecast["label"]
    points = forecast.get("points", [])

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
    if label == "bullish" and resistance_dist_pct is not None:
        if resistance_dist_pct < 2.0:  # Within 2% of resistance
            penalty = (2.0 - resistance_dist_pct) / 2.0 * 0.15  # Up to 15% penalty
            adjusted_confidence = max(0.3, original_confidence - penalty)
            logger.debug(
                f"Bullish near resistance ({resistance_dist_pct:.2f}%), "
                f"confidence {original_confidence:.2f} -> {adjusted_confidence:.2f}"
            )

    # Reduce confidence if predicting bearish near support
    elif label == "bearish" and support_dist_pct is not None:
        if support_dist_pct < 2.0:  # Within 2% of support
            penalty = (2.0 - support_dist_pct) / 2.0 * 0.15  # Up to 15% penalty
            adjusted_confidence = max(0.3, original_confidence - penalty)
            logger.debug(
                f"Bearish near support ({support_dist_pct:.2f}%), "
                f"confidence {original_confidence:.2f} -> {adjusted_confidence:.2f}"
            )

    forecast["confidence"] = adjusted_confidence

    # Add S/R metadata to forecast
    forecast["sr_levels"] = {
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "support_distance_pct": support_dist_pct,
        "resistance_distance_pct": resistance_dist_pct,
        "all_supports": sr_levels.get("all_supports", [])[:5],  # Top 5
        "all_resistances": sr_levels.get("all_resistances", [])[:5],  # Top 5
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
    - Baseline ML forecasts for multiple horizons
    - SuperTrend AI indicator with K-means clustering

    Args:
        symbol: Stock ticker symbol
    """
    logger.info(f"Processing {symbol}...")

    try:
        # Fetch most recent bars (db.fetch_ohlc_bars already returns latest first and sorts ascending)
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)

        if len(df) < settings.min_bars_for_training:
            logger.warning(
                f"Insufficient data for {symbol}: {len(df)} bars "
                f"(need {settings.min_bars_for_training})"
            )
            return

        # Add technical indicators (includes S/R features)
        df = add_technical_features(df)

        # Extract S/R levels for forecast constraints
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        current_price = df["close"].iloc[-1]

        logger.info(
            f"S/R Levels for {symbol}: support={sr_levels.get('nearest_support')}, "
            f"resistance={sr_levels.get('nearest_resistance')}, price={current_price:.2f}"
        )

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
        try:
            supertrend = SuperTrendAI(df)
            st_df, st_info = supertrend.calculate()

            supertrend_data = {
                "supertrend_factor": st_info["target_factor"],
                "supertrend_performance": st_info["performance_index"],
                "supertrend_signal": int(st_df["supertrend_signal"].iloc[-1]),
                "trend_label": st_info["current_trend"],
                "trend_confidence": st_info["signal_strength"],
                "stop_level": float(st_df["supertrend"].iloc[-1]),
                "trend_duration_bars": st_info["trend_duration_bars"],
            }

            logger.info(
                f"SuperTrend AI for {symbol}: "
                f"factor={st_info['target_factor']:.2f}, "
                f"trend={st_info['current_trend']}, "
                f"confidence={st_info['signal_strength']}/10"
            )

            # Store signals in supertrend_signals table if any new signals
            if st_info["signals"]:
                db.upsert_supertrend_signals(symbol, st_info["signals"])

        except Exception as e:
            logger.warning(f"SuperTrend AI failed for {symbol}: {e}")

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

                forecast = {
                    "label": ensemble_pred["label"].lower(),
                    "confidence": ensemble_pred["confidence"],
                    "horizon": horizon,
                    "points": baseline._generate_forecast_points(
                        df["ts"].iloc[-1],
                        df["close"].iloc[-1],
                        ensemble_pred["label"].lower(),
                        ensemble_pred["confidence"],
                        baseline._parse_horizon(horizon),
                        probabilities=ensemble_probs,  # Pass probabilities for directional estimates
                    ),
                    "probabilities": ensemble_probs,
                    "rf_prediction": ensemble_pred.get("rf_prediction"),
                    "gb_prediction": ensemble_pred.get("gb_prediction"),
                    "agreement": ensemble_pred.get("agreement"),
                    "ensemble_type": "RF+GB",
                    "backtest": (
                        backtest_metrics.__dict__ if backtest_metrics else None
                    ),
                    "training_stats": forecaster.training_stats,
                }

                # Apply S/R constraints to forecast
                forecast = apply_sr_constraints(forecast, sr_levels, current_price)
            else:
                # Fallback to baseline forecaster
                baseline_forecaster = BaselineForecaster()
                forecast = baseline_forecaster.generate_forecast(df, horizon)
                forecast["training_stats"] = getattr(
                    baseline_forecaster, "training_stats", None
                )

                # Apply S/R constraints to forecast
                forecast = apply_sr_constraints(forecast, sr_levels, current_price)

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

            # Save to database (include SuperTrend data and S/R levels)
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
            )

            logger.info(
                f"Saved {horizon} forecast for {symbol}: "
                f"{forecast['label']} ({forecast['confidence']:.2%})"
                + (
                    f" [ensemble: RF={forecast.get('rf_prediction')}, "
                    f"GB={forecast.get('gb_prediction')}, "
                    f"agreement={forecast.get('agreement')}]"
                    if use_ensemble
                    else ""
                )
            )
            logger.info(
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
