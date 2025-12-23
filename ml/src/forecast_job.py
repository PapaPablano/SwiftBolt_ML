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
        # Fetch OHLC data
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=500)

        if len(df) < settings.min_bars_for_training:
            logger.warning(
                f"Insufficient data for {symbol}: {len(df)} bars "
                f"(need {settings.min_bars_for_training})"
            )
            return

        # Add technical indicators
        df = add_technical_features(df)

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
                    ),
                    "rf_prediction": ensemble_pred.get("rf_prediction"),
                    "gb_prediction": ensemble_pred.get("gb_prediction"),
                    "agreement": ensemble_pred.get("agreement"),
                    "ensemble_type": "RF+GB",
                    "backtest": (
                        backtest_metrics.__dict__ if backtest_metrics else None
                    ),
                }
            else:
                # Fallback to baseline forecaster
                baseline_forecaster = BaselineForecaster()
                forecast = baseline_forecaster.generate_forecast(df, horizon)

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
                    "conflicting_signals": supertrend_data.get(
                        "conflicting_signals", 0
                    )
                    if supertrend_data
                    else 0,
                }
            )

            # Save to database (include SuperTrend data if available)
            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=forecast["horizon"],
                overall_label=forecast["label"],
                confidence=forecast["confidence"],
                points=forecast["points"],
                supertrend_data=supertrend_data,
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
