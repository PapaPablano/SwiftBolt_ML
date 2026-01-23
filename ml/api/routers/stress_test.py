"""Router for stress testing endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.stress_test import StressTestRequest, StressTestResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

from scripts.run_stress_test import run_stress_test

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/stress-test", response_model=StressTestResponse)
async def run_stress_test_endpoint(request: StressTestRequest):
    """
    Run stress test on a portfolio.
    
    Applies historical scenarios or custom price shocks to assess portfolio risk.
    """
    try:
        if not request.positions or not request.prices:
            raise HTTPException(
                status_code=400,
                detail="positions and prices are required",
            )
        
        if not request.scenario and not request.customShocks:
            raise HTTPException(
                status_code=400,
                detail="Either scenario or customShocks must be provided",
            )
        
        result = run_stress_test(
            positions=request.positions,
            current_prices=request.prices,
            scenario_name=request.scenario,
            custom_shocks=request.customShocks,
            var_level=request.varLevel if request.varLevel is not None else 0.05,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return StressTestResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running stress test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
