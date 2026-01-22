"""
Multi-Horizon Forecast Job.

Generates cascading forecasts across multiple time horizons for each timeframe,
creating a comprehensive predictive portrait from near-term to long-term.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TIMEFRAME_HORIZONS, settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.features.feature_cache import fetch_or_build_features  # noqa: E402
from src.features.support_resistance_detector import (  # noqa: E402
    SupportResistanceDetector,
)
from src.forecast_synthesizer import ForecastSynthesizer  # noqa: E402
from src.models.ensemble_loader import (  # noqa: E402
    EnsemblePredictor,
)
from src.multi_horizon_forecast import (  # noqa: E402
    MultiHorizonForecast,
    build_cascading_consensus,
    calculate_consensus_weights,
    calculate_handoff_confidence,
)
from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def generate_multi_horizon_forecasts(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
) -> Optional[MultiHorizonForecast]:
    """Generate cascading forecasts for a specific symbol and timeframe.

    Args:
        symbol: Stock ticker
        timeframe: Timeframe identifier (e.g., "m15", "h1", "d1")
        df: DataFrame with OHLCV data and indicators

    Returns:
        MultiHorizonForecast with all horizons or None if generation fails
    """
    if timeframe not in TIMEFRAME_HORIZONS:
        logger.warning(
            "Timeframe %s not in TIMEFRAME_HORIZONS config",
            timeframe,
        )
        return None

    config = TIMEFRAME_HORIZONS[timeframe]
    horizons = config["horizons"]
    horizon_days_list = config["horizon_days"]

    if len(df) < 50:
        logger.warning(
            "Insufficient data for %s %s: %s bars",
            symbol,
            timeframe,
            len(df),
        )
        return None

    current_price = float(df["close"].iloc[-1])

    # Calculate indicators
    try:
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)

        supertrend = SuperTrendAI(df)
        st_df, st_info = supertrend.calculate()

        predictor = EnsemblePredictor(
            symbol=symbol,
            timeframe=timeframe,
            use_trained_weights=False,
        )
        ensemble_payload = predictor.predict(df)
        if not ensemble_payload:
            logger.error("No ensemble prediction for %s/%s", symbol, timeframe)
            return None

    except Exception as exc:
        logger.error(
            "Failed to calculate indicators for %s %s: %s",
            symbol,
            timeframe,
            exc,
        )
        return None

    # Convert to synthesizer format
    from src.forecast_job import (  # noqa: E402
        convert_sr_to_synthesizer_format,
        convert_supertrend_to_synthesizer_format,
    )

    sr_response = convert_sr_to_synthesizer_format(sr_levels, current_price)
    st_info_formatted = convert_supertrend_to_synthesizer_format(st_info)

    # Generate forecasts for each horizon
    synthesizer = ForecastSynthesizer()
    forecasts = {}

    for horizon, horizon_days in zip(horizons, horizon_days_list):
        try:
            forecast_result = synthesizer.generate_forecast(
                current_price=current_price,
                df=df,
                supertrend_info=st_info_formatted,
                sr_response=sr_response,
                ensemble_result={
                    "label": ensemble_payload["forecast"],
                    "confidence": ensemble_payload["confidence"],
                    "agreement": ensemble_payload["model_agreements"],
                },
                horizon_days=horizon_days,
                symbol=symbol,
                timeframe=timeframe,
            )
            forecasts[horizon] = forecast_result

            logger.info(
                "%s %s %s: %s target=$%.2f conf=%.2f",
                symbol,
                timeframe,
                horizon,
                forecast_result.direction,
                forecast_result.target,
                forecast_result.confidence,
            )

        except Exception as exc:
            logger.error(
                "Failed to generate %s forecast for %s %s: %s",
                horizon,
                symbol,
                timeframe,
                exc,
            )
            continue

    if not forecasts:
        logger.warning("No forecasts generated for %s %s", symbol, timeframe)
        return None

    # Calculate consensus weights
    base_horizon = horizons[0]
    consensus_weights = calculate_consensus_weights(forecasts, base_horizon)

    # Calculate handoff confidence.
    # Placeholder: rely on local timeframe data.
    # Cross-timeframe cache integration pending.
    handoff_confidence = {
        horizon: forecasts[horizon].confidence
        for horizon in horizons
        if horizon in forecasts
    }

    forecast = MultiHorizonForecast(
        timeframe=timeframe,
        symbol=symbol,
        base_horizon=base_horizon,
        extended_horizons=horizons[1:],
        forecasts=forecasts,
        consensus_weights=consensus_weights,
        handoff_confidence=handoff_confidence,
        generated_at=datetime.utcnow().isoformat(),
        current_price=current_price,
    )

    # Annotate ensemble metadata for downstream persistence
    forecast.metadata = {
        "ensemble_is_trained": predictor.is_trained,
        "ensemble_weights": ensemble_payload.get("weights_used"),
    }

    return forecast


def process_symbol_all_timeframes(
    symbol: str,
) -> Dict[str, MultiHorizonForecast]:
    """Process a symbol across all timeframes.

    Args:
        symbol: Stock ticker

    Returns:
        Dictionary of timeframe -> MultiHorizonForecast
    """
    logger.info("Processing %s across all timeframes...", symbol)

    # Fetch features for all timeframes
    timeframes = list(TIMEFRAME_HORIZONS.keys())
    limits = {
        tf: TIMEFRAME_HORIZONS[tf]["training_bars"]
        for tf in timeframes
    }

    try:
        features_by_tf = fetch_or_build_features(
            db=db,
            symbol=symbol,
            limits=limits,
        )
    except Exception as e:
        logger.error("Failed to fetch features for %s: %s", symbol, e)
        return {}

    # Generate multi-horizon forecasts for each timeframe
    all_forecasts = {}

    for timeframe in timeframes:
        df = features_by_tf.get(timeframe)
        if df is None or len(df) < 50:
            logger.warning(
                "Skipping %s for %s: insufficient data",
                timeframe,
                symbol,
            )
            continue

        mh_forecast = generate_multi_horizon_forecasts(symbol, timeframe, df)
        if mh_forecast:
            all_forecasts[timeframe] = mh_forecast

    # Calculate handoff confidence between timeframes
    timeframe_order = ["m15", "h1", "h4", "d1", "w1"]
    for idx in range(len(timeframe_order) - 1):
        current_tf = timeframe_order[idx]
        next_tf = timeframe_order[idx + 1]

        if current_tf not in all_forecasts or next_tf not in all_forecasts:
            continue

        current_mh = all_forecasts[current_tf]
        next_mh = all_forecasts[next_tf]

        # Update handoff confidence for overlapping horizons
        for horizon in current_mh.forecasts:
            if horizon not in next_mh.forecasts:
                continue

            horizon_idx = (
                current_mh.extended_horizons.index(horizon) + 1
                if horizon in current_mh.extended_horizons
                else 0
            )
            horizon_days = TIMEFRAME_HORIZONS[current_tf]["horizon_days"][
                horizon_idx
            ]

            handoff = calculate_handoff_confidence(
                current_mh.forecasts[horizon],
                next_mh.forecasts[horizon],
                horizon_days=horizon_days,
            )
            current_mh.handoff_confidence[horizon] = handoff

    return all_forecasts


def build_consensus_forecasts(
    all_forecasts: Dict[str, MultiHorizonForecast],
) -> Dict[str, dict]:
    """Build cascading consensus forecasts from all timeframes.

    Args:
        all_forecasts: Dictionary of timeframe -> MultiHorizonForecast

    Returns:
        Dictionary of horizon -> consensus forecast dict
    """
    all_horizons = {
        horizon
        for mh_forecast in all_forecasts.values()
        for horizon in mh_forecast.forecasts
    }

    consensus_forecasts = {}

    for horizon in sorted(all_horizons):
        consensus = build_cascading_consensus(all_forecasts, horizon)
        if consensus:
            consensus_forecasts[horizon] = consensus.to_dict()
            logger.info(
                "Consensus %s: %s target=$%.2f conf=%.2f agreement=%.2f",
                horizon,
                consensus.direction,
                consensus.target,
                consensus.confidence,
                consensus.agreement_score,
            )

    return consensus_forecasts


def store_multi_horizon_forecasts(
    symbol: str,
    all_forecasts: Dict[str, MultiHorizonForecast],
    consensus_forecasts: Dict[str, dict],
) -> None:
    """Store multi-horizon forecasts and consensus outputs."""

    symbol_id = db.get_symbol_id(symbol)

    for timeframe, mh_forecast in all_forecasts.items():
        rows = []
        for horizon, forecast_result in mh_forecast.forecasts.items():
            rows.append(
                {
                    "horizon": horizon,
                    "overall_label": forecast_result.direction.lower(),
                    "confidence": forecast_result.confidence,
                    "target_price": forecast_result.target,
                    "upper_band": forecast_result.upper_band,
                    "lower_band": forecast_result.lower_band,
                    "is_base_horizon": horizon == mh_forecast.base_horizon,
                    "handoff_confidence": mh_forecast.handoff_confidence.get(
                        horizon
                    ),
                    "consensus_weight": mh_forecast.consensus_weights.get(
                        horizon,
                        0.0,
                    ),
                    "key_drivers": forecast_result.key_drivers,
                    "layers_agreeing": forecast_result.layers_agreeing,
                    "reasoning": forecast_result.reasoning,
                    "ensemble_weights": mh_forecast.metadata.get(
                        "ensemble_weights"
                    ),
                    "training_stats": {
                        "ensemble_is_trained": mh_forecast.metadata.get(
                            "ensemble_is_trained"
                        )
                    },
                    "model_agreement": None,
                }
            )

        try:
            db.upsert_multi_horizon_forecasts(
                symbol_id=symbol_id,
                timeframe=timeframe,
                forecasts=rows,
            )
        except Exception as exc:
            logger.error(
                "Failed to store multi-horizon forecasts for %s (%s): %s",
                symbol,
                timeframe,
                exc,
            )

    if not consensus_forecasts:
        return

    consensus_rows = []
    for horizon, consensus in consensus_forecasts.items():
        consensus_rows.append(
            {
                "horizon": horizon,
                "overall_label": consensus["direction"].lower(),
                "confidence": consensus["confidence"],
                "target_price": consensus["target"],
                "upper_band": consensus["upper_band"],
                "lower_band": consensus["lower_band"],
                "contributing_timeframes": consensus[
                    "contributing_timeframes"
                ],
                "agreement_score": consensus["agreement_score"],
                "handoff_quality": consensus["handoff_quality"],
            }
        )

    try:
        db.upsert_consensus_forecasts(
            symbol_id=symbol_id,
            forecasts=consensus_rows,
        )
    except Exception as exc:
        logger.error(
            "Failed to store consensus forecasts for %s: %s",
            symbol,
            exc,
        )


def main():
    """Main entry point for multi-horizon forecast job."""
    parser = argparse.ArgumentParser(
        description="Generate multi-horizon forecasts",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=settings.symbols_to_process,
        help="Symbols to process",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        help="Process only specific timeframe (optional)",
    )

    args = parser.parse_args()

    logger.info("Starting multi-horizon forecast job...")
    logger.info("Processing symbols: %s", args.symbols)

    for symbol in args.symbols:
        try:
            # Generate forecasts for all timeframes
            all_forecasts = process_symbol_all_timeframes(symbol)

            if not all_forecasts:
                logger.warning("No forecasts generated for %s", symbol)
                continue

            # Build consensus forecasts
            consensus_forecasts = build_consensus_forecasts(all_forecasts)

            # Store in database
            store_multi_horizon_forecasts(
                symbol,
                all_forecasts,
                consensus_forecasts,
            )

            logger.info(
                "Completed %s: %s timeframes, %s consensus horizons",
                symbol,
                len(all_forecasts),
                len(consensus_forecasts),
            )

        except Exception as exc:
            logger.error(
                "Failed to process %s: %s",
                symbol,
                exc,
                exc_info=True,
            )
            continue

    logger.info("Multi-horizon forecast job completed")


if __name__ == "__main__":
    main()
