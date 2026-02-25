"""Router for backtesting endpoint."""

import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.models.backtest import (
    BacktestRequest,
    BacktestResponse,
    StrategyBacktestResultsResponse,
)

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

# Import from scripts directory
from scripts.run_backtest import run_backtest

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_supabase_client():
    """Lazy Supabase client for strategy-backtest-results (requires SUPABASE_URL + SUPABASE_KEY)."""
    from supabase import create_client

    from config.settings import settings

    url = getattr(settings, "supabase_url", None) or ""
    key = getattr(settings, "supabase_key", None) or getattr(
        settings, "supabase_service_role_key", None
    )
    if not url or not key:
        return None
    return create_client(url.rstrip("/"), key)


@router.get(
    "/strategy-backtest-results",
    response_model=StrategyBacktestResultsResponse,
    summary="Get strategy backtest result by job ID",
)
async def get_strategy_backtest_results(
    job_id: str = Query(..., description="Backtest job UUID from queue response"),
) -> StrategyBacktestResultsResponse:
    """
    Return stored backtest result for a completed job.

    Fetches from `strategy_backtest_results` (and job metadata from
    `strategy_backtest_jobs`). Returns 404 if no result exists for the job,
    and 503 if Supabase is not configured.
    """
    client = _get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Strategy backtest results require SUPABASE_URL and SUPABASE_KEY.",
        )

    # Fetch result by job_id
    result_resp = (
        client.table("strategy_backtest_results")
        .select("id, job_id, metrics, trades, equity_curve, created_at")
        .eq("job_id", job_id)
        .limit(1)
        .execute()
    )
    if not result_resp.data or len(result_resp.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest result found for job_id={job_id}.",
        )
    row = result_resp.data[0]
    metrics = row.get("metrics") or {}
    trades = row.get("trades") or []
    equity_curve = row.get("equity_curve") or []

    # Fetch job for status and symbol/date range
    job_resp = (
        client.table("strategy_backtest_jobs")
        .select("id, status, symbol, start_date, end_date, error_message")
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    status = "unknown"
    symbol: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    error_msg: Optional[str] = None
    if job_resp.data and len(job_resp.data) > 0:
        job = job_resp.data[0]
        status = job.get("status") or "unknown"
        symbol = job.get("symbol")
        start_date = str(job["start_date"]) if job.get("start_date") else None
        end_date = str(job["end_date"]) if job.get("end_date") else None
        error_msg = job.get("error_message")

    return StrategyBacktestResultsResponse(
        jobId=job_id,
        status=status,
        symbol=symbol,
        startDate=start_date,
        endDate=end_date,
        metrics=metrics,
        trades=trades,
        equityCurve=equity_curve,
        error=error_msg,
    )


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
