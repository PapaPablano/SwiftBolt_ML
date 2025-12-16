"""Main ML forecasting job that generates predictions for all symbols."""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from src.models.baseline_forecaster import BaselineForecaster

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_symbol(symbol: str) -> None:
    """
    Process a single symbol: fetch data, train model, generate forecasts.

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

        # Generate forecasts for each horizon
        for horizon in settings.forecast_horizons:
            logger.info(f"Generating {horizon} forecast for {symbol}")

            # Create forecaster
            forecaster = BaselineForecaster()

            # Generate forecast
            forecast = forecaster.generate_forecast(df, horizon)

            # Save to database
            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=forecast["horizon"],
                overall_label=forecast["label"],
                confidence=forecast["confidence"],
                points=forecast["points"],
            )

            logger.info(
                f"Saved {horizon} forecast for {symbol}: "
                f"{forecast['label']} ({forecast['confidence']:.2%})"
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
