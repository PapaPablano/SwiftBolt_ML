"""Router for walk-forward optimization endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.walk_forward import WalkForwardRequest, WalkForwardResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from scripts directory
from scripts.run_walk_forward import run_walk_forward

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/walk-forward-optimize", response_model=WalkForwardResponse)
async def run_walk_forward_endpoint(request: WalkForwardRequest):
    """
    Run walk-forward optimization for ML forecasters.
    
    Tests forecaster performance over multiple time windows.
    """
    try:
        result = run_walk_forward(
            symbol=request.symbol.upper(),
            horizon=request.horizon,
            forecaster_type=request.forecaster,
            timeframe=request.timeframe or "d1",
            train_window=request.trainWindow,
            test_window=request.testWindow,
            step_size=request.stepSize,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return WalkForwardResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running walk-forward optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
