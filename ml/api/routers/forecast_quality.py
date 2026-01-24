"""Router for forecast quality endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.forecast_quality import ForecastQualityRequest, ForecastQualityResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from scripts directory
from scripts.run_forecast_quality import get_forecast_quality

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/forecast-quality", response_model=ForecastQualityResponse)
async def get_forecast_quality_endpoint(request: ForecastQualityRequest):
    """
    Get forecast quality metrics for a symbol.
    
    Returns quality score, confidence, model agreement, and any issues.
    """
    try:
        result = get_forecast_quality(
            symbol=request.symbol.upper(),
            horizon=request.horizon or "1D",
            timeframe=request.timeframe or "d1",
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return ForecastQualityResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting forecast quality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
