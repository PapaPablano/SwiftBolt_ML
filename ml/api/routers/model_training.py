"""Router for model training endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.model_training import ModelTrainingRequest, ModelTrainingResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from scripts directory
from scripts.run_model_training import run_model_training

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/train-model", response_model=ModelTrainingResponse)
async def train_model_endpoint(request: ModelTrainingRequest):
    """
    Train ML model for a symbol/timeframe.
    
    Trains an ensemble model and returns training metrics.
    """
    try:
        result = run_model_training(
            symbol=request.symbol.upper(),
            timeframe=request.timeframe or "d1",
            lookback_days=request.lookbackDays or 90,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return ModelTrainingResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
