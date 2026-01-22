"""Router for technical indicators endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from api.models.technical_indicators import TechnicalIndicatorsResponse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.get_technical_indicators import get_latest_indicators

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/technical-indicators", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(
    symbol: str = Query(..., description="Stock ticker symbol"),
    timeframe: str = Query("d1", description="Timeframe (d1, h1, m15, etc.)"),
    lookback: int = Query(500, description="Number of bars to fetch"),
):
    """
    Get technical indicators for a symbol/timeframe.
    
    Returns all calculated technical indicators for the latest bar.
    """
    try:
        result = get_latest_indicators(
            symbol=symbol.upper(),
            timeframe=timeframe,
            lookback_bars=lookback,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return TechnicalIndicatorsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting technical indicators: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
