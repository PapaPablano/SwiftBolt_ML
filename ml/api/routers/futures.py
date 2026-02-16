"""Router for Yahoo Finance futures data endpoints."""

import json
import logging
import os
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

_redis_client = None

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

TTL_BY_TIMEFRAME = {
    "1m": 30,
    "15m": 60,
    "1h": 120,
    "4h": 300,
    "1d": 900,
    "1w": 1800,
}


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )
        _redis_client.ping()
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None


def _cache_key(
    symbol: str, mode: str, timeframe: str, start_date: str, end_date: str
) -> str:
    return f"futures:{symbol}:{mode}:{timeframe}:{start_date}:{end_date}"


SUPPORTED_ROOTS = {
    "ES",
    "NQ",
    "GC",
    "CL",
    "ZC",
    "ZS",
    "ZW",
    "HE",
    "LE",
    "HG",
    "SI",
    "PL",
    "PA",
}


def _normalize_futures_symbol(symbol: str) -> tuple[str, str]:
    """
    Normalize futures symbol to root.

    Handles:
    - ES2!, ES1!, ES! -> ES (continuous)
    - GCH6, GCZ4 -> GC
    - ES -> ES (already normalized)

    Returns: (root, original_symbol)
    """
    original = symbol.upper().strip()

    if original in SUPPORTED_ROOTS:
        return original, original

    for root in SUPPORTED_ROOTS:
        if original.startswith(root):
            return root, original

    import re

    match = re.match(r"^([A-Z]+)", original)
    if match:
        potential_root = match.group(1)
        if potential_root in SUPPORTED_ROOTS:
            return potential_root, original

    return original, original


def _aggregate_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1h bars to 4h."""
    if df.empty or "timestamp" not in df.columns:
        return df
    df = df.set_index("timestamp")
    agg = (
        df.resample("4h")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )
    agg = agg.reset_index()
    return agg


def _aggregate_to_1w(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1d bars to 1w."""
    if df.empty or "timestamp" not in df.columns:
        return df
    df = df.set_index("timestamp")
    agg = (
        df.resample("1w")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )
    agg = agg.reset_index()
    return agg


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
    - Results are cached in Redis with TTL by timeframe
    - Automatically handles TradingView-style symbols (ES2! -> ES)
    - 4h derived from 1h, 1w from 1d if not available directly
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    root, original = _normalize_futures_symbol(symbol)
    if root not in SUPPORTED_ROOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown futures symbol: {symbol}. Supported: {', '.join(SUPPORTED_ROOTS)}",
        )

    cache_key = _cache_key(root, mode, timeframe, start_date, end_date)
    r = _get_redis()

    if r:
        cached = r.get(cache_key)
        if cached:
            logger.info(f"Cache hit for {cache_key}")
            data = json.loads(cached)
            return FuturesBarResponse(**data)

    client = get_client()

    resolution = timeframe
    needs_derivation = False

    if timeframe == "4h":
        resolution = "1h"
        needs_derivation = True
    elif timeframe == "1w":
        resolution = "1d"
        needs_derivation = True

    if mode == "continuous":
        df = client.get_continuous_contract(
            root=root,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )
        display_symbol = f"{root}.v.0"
    else:
        df = client.get_expiry_contract(
            symbol=root,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )
        display_symbol = f"{root}.v.0"

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {display_symbol} from {start_date} to {end_date}",
        )

    if needs_derivation and timeframe == "4h":
        df = _aggregate_to_4h(df)
    elif needs_derivation and timeframe == "1w":
        df = _aggregate_to_1w(df)

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

    response_data = {
        "symbol": display_symbol,
        "mode": mode,
        "bars": bars,
        "start_date": start_date,
        "end_date": end_date,
    }

    if r:
        ttl = TTL_BY_TIMEFRAME.get(timeframe, 120)
        r.setex(cache_key, ttl, json.dumps(response_data))
        logger.info(f"Cached {cache_key} with TTL {ttl}s")

    return FuturesBarResponse(**response_data)


@router.post("/futures/backfill")
async def backfill_futures_bars(request: BackfillRequest) -> BackfillResponse:
    """
    Backfill futures OHLCV bars from Yahoo Finance into Supabase.

    Fetches historical data and upserts into ohlc_bars_v2 table.
    - Supports TradingView-style symbols (ES2! -> ES)
    - Supports timeframe derivation (4h from 1h, 1w from 1d)
    """
    root, original = _normalize_futures_symbol(request.symbol)
    if root not in SUPPORTED_ROOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown futures symbol: {request.symbol}. Supported: {', '.join(SUPPORTED_ROOTS)}",
        )

    client = get_client()
    db = SupabaseDatabase()

    end_date = request.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = request.start_date or (datetime.now() - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )

    resolution = request.timeframe
    if request.timeframe == "4h":
        resolution = "1h"
    elif request.timeframe == "1w":
        resolution = "1d"

    if request.mode == "continuous":
        df = client.get_continuous_contract(
            root=root,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )
        db_symbol = f"{root}.v.0"
    else:
        df = client.get_expiry_contract(
            symbol=root,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )
        db_symbol = f"{root}.v.0"

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {db_symbol}",
        )

    if request.timeframe == "4h":
        df = _aggregate_to_4h(df)
    elif request.timeframe == "1w":
        df = _aggregate_to_1w(df)

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
