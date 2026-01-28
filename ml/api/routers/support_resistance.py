"""Router for Support and Resistance indicator endpoint."""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.models.support_resistance import (
    LogisticLevel,
    PolynomialLevel,
    PivotLevel,
    SRSignal,
    SupportResistanceResponse,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.features.support_resistance_detector import SupportResistanceDetector

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/support-resistance/health")
async def support_resistance_health():
    """
    Health check for support-resistance endpoint.
    Returns immediately without doing heavy calculations.
    """
    return {"status": "healthy", "service": "support-resistance"}


@router.get("/support-resistance", response_model=SupportResistanceResponse)
async def get_support_resistance(
    symbol: str = Query(..., description="Stock ticker symbol"),
    timeframe: str = Query("d1", description="Timeframe (d1, h1, m15, etc.)"),
    lookback: int = Query(252, description="Number of bars to analyze"),
):
    """
    Get support and resistance levels for a symbol/timeframe.

    Returns comprehensive S/R analysis using 3 indicators:
    - Pivot Levels (multi-timeframe)
    - Polynomial Regression (trending S/R with forecasts)
    - Logistic Regression (ML-based probability levels)

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT)
        timeframe: Timeframe for analysis (d1, h1, m15, etc.)
        lookback: Number of bars to analyze (default 252 for daily = 1 year)

    Returns:
        SupportResistanceResponse with all S/R levels and analysis
    """
    start_time = time.time()
    try:
        logger.info(
            f"[SR] Starting S/R analysis for {symbol}/{timeframe} (lookback={lookback})"
        )

        # Fetch OHLC data from Supabase
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol=symbol.upper(), timeframe=timeframe, limit=lookback)

        if df is None or df.empty:
            logger.warning(f"[SR] No data available for {symbol}/{timeframe}")
            raise HTTPException(
                status_code=404, detail=f"No data available for {symbol}/{timeframe}"
            )

        logger.info(f"[SR] Fetched {len(df)} bars for {symbol}/{timeframe}")

        # Run S/R detector
        detector = SupportResistanceDetector()
        sr_result = detector.find_all_levels(df)

        current_price = float(df["close"].iloc[-1])

        # Get timestamp from last bar
        last_bar = df.iloc[-1]
        if "ts" in df.columns:
            timestamp = last_bar["ts"]
            if hasattr(timestamp, "isoformat"):
                last_bar_time = timestamp.isoformat()
            else:
                last_bar_time = str(timestamp)
        else:
            last_bar_time = datetime.utcnow().isoformat()

        # Extract pivot levels
        pivot_levels = []
        for indicator in sr_result.get("indicators", {}).get("pivot_levels", {}).get("data", []):
            if isinstance(indicator, dict):
                pivot_levels.append(
                    PivotLevel(
                        period=indicator.get("period", 0),
                        level_high=indicator.get("level_high"),
                        level_low=indicator.get("level_low"),
                        high_status=indicator.get("high_status"),
                        low_status=indicator.get("low_status"),
                    )
                )

        # Extract polynomial levels
        poly_indicator = sr_result.get("indicators", {}).get("polynomial", {})
        poly_support = None
        poly_resistance = None

        # Helper function to determine trend from slope
        def get_trend(slope: float) -> str:
            if slope > 0.001:
                return "rising"
            elif slope < -0.001:
                return "falling"
            else:
                return "flat"

        # Use correct key names: support/resistance (mapped from current_support/current_resistance)
        if poly_indicator.get("support") is not None:
            support_slope = poly_indicator.get("support_slope", 0)
            poly_support = PolynomialLevel(
                level=poly_indicator["support"],
                slope=support_slope,
                trend=poly_indicator.get("support_trend", get_trend(support_slope)),
                forecast=poly_indicator.get("forecast_support"),
            )

        if poly_indicator.get("resistance") is not None:
            resistance_slope = poly_indicator.get("resistance_slope", 0)
            poly_resistance = PolynomialLevel(
                level=poly_indicator["resistance"],
                slope=resistance_slope,
                trend=poly_indicator.get("resistance_trend", get_trend(resistance_slope)),
                forecast=poly_indicator.get("forecast_resistance"),
            )

        # Extract logistic levels
        logistic_indicator = sr_result.get("indicators", {}).get("logistic", {})
        logistic_supports = []
        logistic_resistances = []

        for level_data in logistic_indicator.get("support_levels", []):
            logistic_supports.append(
                LogisticLevel(
                    level=level_data.get("level", 0),
                    probability=level_data.get("probability", 0),
                    times_respected=level_data.get("times_respected", 0),
                )
            )

        for level_data in logistic_indicator.get("resistance_levels", []):
            logistic_resistances.append(
                LogisticLevel(
                    level=level_data.get("level", 0),
                    probability=level_data.get("probability", 0),
                    times_respected=level_data.get("times_respected", 0),
                )
            )

        # Extract signals
        signals = []
        for signal_data in logistic_indicator.get("signals", []):
            signals.append(
                SRSignal(
                    signal=signal_data.get("signal", "unknown"),
                    level=signal_data.get("level", 0),
                    confirmation=signal_data.get("confirmation"),
                )
            )

        # Build response
        response = SupportResistanceResponse(
            symbol=symbol.upper(),
            current_price=current_price,
            last_updated=last_bar_time,
            nearest_support=sr_result.get("nearest_support"),
            nearest_resistance=sr_result.get("nearest_resistance"),
            support_distance_pct=sr_result.get("support_distance_pct"),
            resistance_distance_pct=sr_result.get("resistance_distance_pct"),
            bias=sr_result.get("bias"),
            pivot_levels=pivot_levels,
            polynomial_support=poly_support,
            polynomial_resistance=poly_resistance,
            logistic_supports=logistic_supports,
            logistic_resistances=logistic_resistances,
            all_supports=sr_result.get("all_supports", []),
            all_resistances=sr_result.get("all_resistances", []),
            signals=signals,
            raw_indicators=sr_result.get("indicators", {}),
        )

        elapsed = time.time() - start_time
        logger.info(f"[SR] Completed S/R analysis in {elapsed:.2f}s for {symbol}/{timeframe}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SR] Error in S/R analysis for {symbol}/{timeframe}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing support/resistance: {str(e)}")
