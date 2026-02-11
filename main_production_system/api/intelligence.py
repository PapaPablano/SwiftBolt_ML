"""
FastAPI endpoints for Perplexity intelligence
Integrates with PerplexityService for API access
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List

from ..data_sources.perplexity_service import PerplexityService
from ..connectors.perplexity_pipeline import PerplexityPipeline


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/market/{symbol}")
async def get_market_intelligence(symbol: str):
    """Get market intelligence for a single symbol"""
    try:
        async with PerplexityService() as service:
            result = await service.get_market_intelligence([symbol])
        sym = symbol.upper().strip()
        payload = result.get(sym)
        if payload is None:
            return {"symbol": sym, "sentiment": "neutral", "confidence": 0.5, "analysis": "No data"}
        return {"symbol": sym, **payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market/batch")
async def get_batch_intelligence(symbols: List[str]):
    """Get market intelligence for multiple symbols"""
    try:
        async with PerplexityService() as service:
            result = await service.get_market_intelligence(symbols)
        # Convert to list of records [{symbol, sentiment, confidence, analysis}]
        records = []
        for sym, payload in result.items():
            records.append({"symbol": sym, **payload})
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{sector}")
async def get_sector_research(sector: str, depth: str = "comprehensive"):
    """Get sector research"""
    try:
        async with PerplexityService() as service:
            # Provide a basic sector research using the chat endpoint
            result = await service.research_sector(sector, depth)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/start")
async def start_sentiment_monitoring(
    background_tasks: BackgroundTasks,
    symbols: List[str],
    duration_hours: int = 24,
):
    """Start background sentiment monitoring for symbols"""
    try:
        pipeline = PerplexityPipeline({})
        if background_tasks is None:
            # Run fire-and-forget (not ideal; recommend BackgroundTasks)
            import asyncio
            asyncio.create_task(pipeline.monitor_market_sentiment(symbols, duration_hours))
        else:
            background_tasks.add_task(pipeline.monitor_market_sentiment, symbols, duration_hours)
        return {
            "status": "started",
            "symbols": symbols,
            "duration_hours": duration_hours,
            "message": f"Sentiment monitoring started for {len(symbols)} symbols",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitor/status")
async def get_monitor_status():
    """Get status of ongoing sentiment monitoring"""
    # Placeholder status; wire to storage/metrics if available
    return {
        "active_monitors": 0,
        "last_update": "N/A",
        "symbols_tracked": [],
    }


@router.get("/news/{query}")
async def search_news(query: str, max_results: int = 10):
    """Search for news related to a query"""
    try:
        # Use sync facade for simplicity
        from ..connectors.perplexity_connector import PerplexityConnector

        conn = PerplexityConnector()
        df = conn.search_news(query, max_results)
        return df.to_dict("records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
