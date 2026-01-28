"""Router for technical indicators endpoint."""

import logging
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from api.models.technical_indicators import TechnicalIndicatorsResponse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.get_technical_indicators import get_latest_indicators

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/technical-indicators/health")
async def technical_indicators_health():
    """
    Health check for technical indicators endpoint.
    Returns immediately without doing heavy calculations.
    """
    return {"status": "healthy", "service": "technical-indicators"}


@router.get("/technical-indicators", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(
    symbol: str = Query(..., description="Stock ticker symbol"),
    timeframe: str = Query("d1", description="Timeframe (d1, h1, m15, etc.)"),
    lookback: int = Query(500, description="Number of bars to fetch"),
):
    """
    Get technical indicators for a symbol/timeframe.

    Returns all calculated technical indicators for the latest bar.
    May take up to 60 seconds for first calculation.
    """
    start_time = time.time()
    try:
        logger.info(f"[TI] Starting calculation for {symbol}/{timeframe} (lookback={lookback})")

        result = get_latest_indicators(
            symbol=symbol.upper(),
            timeframe=timeframe,
            lookback_bars=lookback,
        )

        elapsed = time.time() - start_time
        logger.info(f"[TI] Calculation completed in {elapsed:.1f}s for {symbol}/{timeframe}")

        if "error" in result:
            logger.error(f"[TI] Indicator error for {symbol}: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])

        return TechnicalIndicatorsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[TI] Error after {elapsed:.1f}s for {symbol}/{timeframe}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
