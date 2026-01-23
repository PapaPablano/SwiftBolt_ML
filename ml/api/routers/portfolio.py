"""Router for portfolio optimization endpoint."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.portfolio import PortfolioOptimizeRequest, PortfolioOptimizeResponse

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

from scripts.optimize_portfolio import optimize_portfolio

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/portfolio-optimize", response_model=PortfolioOptimizeResponse)
async def optimize_portfolio_endpoint(request: PortfolioOptimizeRequest):
    """
    Optimize portfolio allocation using Modern Portfolio Theory.
    
    Methods: max_sharpe, min_variance, risk_parity, efficient
    """
    try:
        if not request.symbols:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
        
        if request.method == "efficient" and request.targetReturn is None:
            raise HTTPException(
                status_code=400,
                detail="targetReturn is required for efficient method",
            )
        
        result = optimize_portfolio(
            symbols=[s.upper() for s in request.symbols],
            method=request.method,
            lookback_days=request.lookbackDays or 252,
            risk_free_rate=request.riskFreeRate or 0.02,
            target_return=request.targetReturn,
            min_weight=request.minWeight or 0.0,
            max_weight=request.maxWeight or 1.0,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return PortfolioOptimizeResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
