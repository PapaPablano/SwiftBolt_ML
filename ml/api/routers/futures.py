"""Router for Yahoo Finance futures data endpoints."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.yahoo_futures_client import get_client
from src.data.supabase_db import SupabaseDatabase

logger = logging.getLogger(__name__)
router = APIRouter()


class FuturesBarResponse(BaseModel):
    symbol: str
    mode: str
    bars: list[dict]
    start_date: str
    end_date: str


class BackfillRequest(BaseModel):
    symbol: str
    mode: str
    timeframe: str = "1d"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BackfillResponse(BaseModel):
    status: str
    symbol: str
    bars_inserted: int
    start_date: str
    end_date: str


@router.get("/futures/bars")
async def get_futures_bars(
    symbol: str = Query(..., description="Futures symbol (e.g., ES, GC, or GCZ4)"),
    mode: str = Query(
        "continuous",
        description="Mode: 'continuous' for root (ES.v.0), 'contract' for specific expiry",
    ),
    timeframe: str = Query("1d", description="Timeframe: 1m, 15m, 1h, 4h, 1d, 1w"),
    start_date: Optional[str] = Query(
        None, description="Start date (YYYY-MM-DD), defaults to 1 year ago"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (YYYY-MM-DD), defaults to today"
    ),
) -> FuturesBarResponse:
    """
    Get OHLCV bars for futures from Yahoo Finance.

    - mode='continuous': Use root symbol (ES, GC, NQ) - returns front-month continuous contract
    - mode='contract': Use full contract symbol (falls back to continuous)
    """
    client = get_client()

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    root = symbol.upper()
    if mode == "continuous":
        df = client.get_continuous_contract(
            root=root,
            resolution=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        display_symbol = f"{root}.v.0"
    else:
        df = client.get_expiry_contract(
            symbol=symbol.upper(),
            resolution=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        display_symbol = symbol.upper()

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {display_symbol} from {start_date} to {end_date}",
        )

    bars = []
    for _, row in df.iterrows():
        bars.append(
            {
                "timestamp": row["timestamp"].isoformat()
                if isinstance(row["timestamp"], datetime)
                else str(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
            }
        )

    return FuturesBarResponse(
        symbol=display_symbol,
        mode=mode,
        bars=bars,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/futures/backfill")
async def backfill_futures_bars(request: BackfillRequest) -> BackfillResponse:
    """
    Backfill futures OHLCV bars from Yahoo Finance into Supabase.

    Fetches historical data and upserts into ohlc_bars_v2 table.
    """
    client = get_client()

    db = SupabaseDatabase()

    end_date = request.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = request.start_date or (datetime.now() - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )

    if request.mode == "continuous":
        df = client.get_continuous_contract(
            root=request.symbol.upper(),
            resolution=request.timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        db_symbol = f"{request.symbol.upper()}.v.0"
    else:
        df = client.get_expiry_contract(
            symbol=request.symbol.upper(),
            resolution=request.timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        db_symbol = request.symbol.upper()

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {db_symbol}",
        )

    records = []
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = pd.to_datetime(ts)
        ts = ts.replace(tzinfo=None) if ts.tzinfo else ts

        records.append(
            {
                "symbol_id": db_symbol,
                "ts": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                "timeframe": request.timeframe,
            }
        )

    try:
        db.client.table("ohlc_bars_v2").upsert(
            records, on_conflict="symbol_id,ts,timeframe"
        ).execute()
        bars_inserted = len(records)
    except Exception as e:
        logger.error(f"Error upserting futures bars: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to insert bars: {str(e)}")

    return BackfillResponse(
        status="success",
        symbol=db_symbol,
        bars_inserted=bars_inserted,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/futures/roots")
async def get_futures_roots():
    """Get list of supported futures roots."""
    client = get_client()
    return {"roots": client.get_futures_roots()}


@router.get("/futures/health")
async def futures_health():
    """Health check for futures endpoint."""
    try:
        client = get_client()
        return {"status": "healthy", "provider": "yahoo_finance"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
