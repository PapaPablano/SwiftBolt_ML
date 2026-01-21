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
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TIMEFRAME_HORIZONS, settings
from src.data.supabase_db import db
from src.features.feature_cache import fetch_or_build_features
from src.features.support_resistance_detector import SupportResistanceDetector
from src.forecast_synthesizer import ForecastSynthesizer
from src.models.enhanced_ensemble_integration import get_production_ensemble
from src.multi_horizon_forecast import (
    MultiHorizonForecast,
    build_cascading_consensus,
    calculate_consensus_weights,
    calculate_handoff_confidence,
)
from src.strategies.supertrend_ai import SuperTrendAI

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
    """
    Generate cascading forecasts for a specific symbol and timeframe.
    
    Args:
        symbol: Stock ticker
        timeframe: Timeframe identifier (e.g., "m15", "h1", "d1")
        df: DataFrame with OHLCV data and indicators
        
    Returns:
        MultiHorizonForecast with all horizons or None if generation fails
    """
    if timeframe not in TIMEFRAME_HORIZONS:
        logger.warning(f"Timeframe {timeframe} not in TIMEFRAME_HORIZONS config")
        return None
    
    config = TIMEFRAME_HORIZONS[timeframe]
    horizons = config["horizons"]
    horizon_days_list = config["horizon_days"]
    
    if len(df) < 50:
        logger.warning(
            f"Insufficient data for {symbol} {timeframe}: {len(df)} bars"
        )
        return None
    
    current_price = float(df["close"].iloc[-1])
    
    # Calculate indicators
    try:
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        
        supertrend = SuperTrendAI(df)
        st_df, st_info = supertrend.calculate()
        
        # Get ensemble prediction
        ensemble = get_production_ensemble()
        ensemble_result = ensemble.predict(df)
        
    except Exception as e:
        logger.error(
            f"Failed to calculate indicators for {symbol} {timeframe}: {e}"
        )
        return None
    
    # Convert to synthesizer format
    from src.forecast_job import (
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
                ensemble_result=ensemble_result,
                horizon_days=horizon_days,
                symbol=symbol,
                timeframe=timeframe,
            )
            forecasts[horizon] = forecast_result
            
            logger.info(
                f"{symbol} {timeframe} {horizon}: "
                f"{forecast_result.direction} "
                f"target=${forecast_result.target:.2f} "
                f"conf={forecast_result.confidence:.2f}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to generate {horizon} forecast for "
                f"{symbol} {timeframe}: {e}"
            )
            continue
    
    if not forecasts:
        logger.warning(
            f"No forecasts generated for {symbol} {timeframe}"
        )
        return None
    
    # Calculate consensus weights
    base_horizon = horizons[0]
    consensus_weights = calculate_consensus_weights(forecasts, base_horizon)
    
    # Calculate handoff confidence (placeholder - would need next timeframe data)
    handoff_confidence = {}
    for horizon in horizons:
        if horizon in forecasts:
            # For now, use forecast confidence as handoff confidence
            # In full implementation, would compare with next timeframe
            handoff_confidence[horizon] = forecasts[horizon].confidence
    
    return MultiHorizonForecast(
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


def process_symbol_all_timeframes(symbol: str) -> Dict[str, MultiHorizonForecast]:
    """
    Process a symbol across all timeframes.
    
    Args:
        symbol: Stock ticker
        
    Returns:
        Dictionary of timeframe -> MultiHorizonForecast
    """
    logger.info(f"Processing {symbol} across all timeframes...")
    
    # Fetch features for all timeframes
    timeframes = list(TIMEFRAME_HORIZONS.keys())
    limits = {tf: TIMEFRAME_HORIZONS[tf]["training_bars"] for tf in timeframes}
    
    try:
        features_by_tf = fetch_or_build_features(
            db=db,
            symbol=symbol,
            limits=limits,
        )
    except Exception as e:
        logger.error(f"Failed to fetch features for {symbol}: {e}")
        return {}
    
    # Generate multi-horizon forecasts for each timeframe
    all_forecasts = {}
    
    for timeframe in timeframes:
        df = features_by_tf.get(timeframe)
        if df is None or len(df) < 50:
            logger.warning(
                f"Skipping {timeframe} for {symbol}: insufficient data"
            )
            continue
        
        mh_forecast = generate_multi_horizon_forecasts(symbol, timeframe, df)
        if mh_forecast:
            all_forecasts[timeframe] = mh_forecast
    
    # Calculate handoff confidence between timeframes
    timeframe_order = ["m15", "h1", "h4", "d1", "w1"]
    for i in range(len(timeframe_order) - 1):
        current_tf = timeframe_order[i]
        next_tf = timeframe_order[i + 1]
        
        if current_tf not in all_forecasts or next_tf not in all_forecasts:
            continue
        
        current_mh = all_forecasts[current_tf]
        next_mh = all_forecasts[next_tf]
        
        # Update handoff confidence for overlapping horizons
        for horizon in current_mh.forecasts.keys():
            if horizon in next_mh.forecasts:
                handoff = calculate_handoff_confidence(
                    current_mh.forecasts[horizon],
                    next_mh.forecasts[horizon],
                    horizon_days=TIMEFRAME_HORIZONS[current_tf]["horizon_days"][
                        current_mh.extended_horizons.index(horizon) + 1
                        if horizon in current_mh.extended_horizons
                        else 0
                    ],
                )
                current_mh.handoff_confidence[horizon] = handoff
    
    return all_forecasts


def build_consensus_forecasts(
    all_forecasts: Dict[str, MultiHorizonForecast]
) -> Dict[str, dict]:
    """
    Build cascading consensus forecasts from all timeframes.
    
    Args:
        all_forecasts: Dictionary of timeframe -> MultiHorizonForecast
        
    Returns:
        Dictionary of horizon -> consensus forecast dict
    """
    # Collect all unique horizons
    all_horizons = set()
    for mh_forecast in all_forecasts.values():
        all_horizons.update(mh_forecast.forecasts.keys())
    
    consensus_forecasts = {}
    
    for horizon in sorted(all_horizons):
        consensus = build_cascading_consensus(all_forecasts, horizon)
        if consensus:
            consensus_forecasts[horizon] = consensus.to_dict()
            logger.info(
                f"Consensus {horizon}: {consensus.direction} "
                f"target=${consensus.target:.2f} "
                f"conf={consensus.confidence:.2f} "
                f"agreement={consensus.agreement_score:.2f}"
            )
    
    return consensus_forecasts


def store_multi_horizon_forecasts(
    symbol: str,
    all_forecasts: Dict[str, MultiHorizonForecast],
    consensus_forecasts: Dict[str, dict],
) -> None:
    """
    Store multi-horizon forecasts in the database.
    
    Args:
        symbol: Stock ticker
        all_forecasts: All timeframe forecasts
        consensus_forecasts: Consensus forecasts by horizon
    """
    symbol_id = db.get_symbol_id(symbol)
    
    # Store each timeframe's multi-horizon forecast
    for timeframe, mh_forecast in all_forecasts.items():
        for horizon, forecast_result in mh_forecast.forecasts.items():
            try:
                # Store as regular forecast with extended metadata
                db.upsert_forecast(
                    symbol_id=symbol_id,
                    horizon=horizon,
                    timeframe=timeframe,
                    label=forecast_result.direction.lower(),
                    confidence=forecast_result.confidence,
                    target_price=forecast_result.target,
                    upper_band=forecast_result.upper_band,
                    lower_band=forecast_result.lower_band,
                    reasoning=forecast_result.reasoning,
                    metadata={
                        "is_base_horizon": horizon == mh_forecast.base_horizon,
                        "handoff_confidence": mh_forecast.handoff_confidence.get(
                            horizon, 0.0
                        ),
                        "consensus_weight": mh_forecast.consensus_weights.get(
                            horizon, 0.0
                        ),
                        "key_drivers": forecast_result.key_drivers,
                        "layers_agreeing": forecast_result.layers_agreeing,
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to store {timeframe} {horizon} forecast: {e}"
                )
    
    # Store consensus forecasts
    for horizon, consensus in consensus_forecasts.items():
        try:
            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=horizon,
                timeframe="consensus",
                label=consensus["direction"].lower(),
                confidence=consensus["confidence"],
                target_price=consensus["target"],
                upper_band=consensus["upper_band"],
                lower_band=consensus["lower_band"],
                reasoning=f"Consensus from {len(consensus['contributing_timeframes'])} timeframes",
                metadata={
                    "is_consensus": True,
                    "contributing_timeframes": consensus["contributing_timeframes"],
                    "timeframe_weights": consensus["timeframe_weights"],
                    "agreement_score": consensus["agreement_score"],
                    "handoff_quality": consensus["handoff_quality"],
                },
            )
        except Exception as e:
            logger.error(f"Failed to store consensus {horizon} forecast: {e}")


def main():
    """Main entry point for multi-horizon forecast job."""
    parser = argparse.ArgumentParser(
        description="Generate multi-horizon forecasts"
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
    logger.info(f"Processing symbols: {args.symbols}")
    
    for symbol in args.symbols:
        try:
            # Generate forecasts for all timeframes
            all_forecasts = process_symbol_all_timeframes(symbol)
            
            if not all_forecasts:
                logger.warning(f"No forecasts generated for {symbol}")
                continue
            
            # Build consensus forecasts
            consensus_forecasts = build_consensus_forecasts(all_forecasts)
            
            # Store in database
            store_multi_horizon_forecasts(
                symbol, all_forecasts, consensus_forecasts
            )
            
            logger.info(
                f"Completed {symbol}: "
                f"{len(all_forecasts)} timeframes, "
                f"{len(consensus_forecasts)} consensus horizons"
            )
            
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}", exc_info=True)
            continue
    
    logger.info("Multi-horizon forecast job completed")


if __name__ == "__main__":
    main()
