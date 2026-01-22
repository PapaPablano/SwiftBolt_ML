"""Router for backtesting endpoint."""

import json
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models.backtest import BacktestRequest, BacktestResponse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.run_backtest import run_backtest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/backtest-strategy", response_model=BacktestResponse)
async def run_backtest_endpoint(request: BacktestRequest):
    """
    Run a backtest for a trading strategy.
    
    Supports strategies: supertrend_ai, sma_crossover, buy_and_hold
    """
    try:
        # Convert Pydantic model to dict for the script function
        result = run_backtest(
            symbol=request.symbol.upper(),
            strategy_name=request.strategy,
            start_date=request.startDate,
            end_date=request.endDate,
            timeframe=request.timeframe or "d1",
            initial_capital=request.initialCapital or 10000,
            strategy_params=request.params or {},
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return BacktestResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running backtest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
