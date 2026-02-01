"""Router for FinViz news with sentiment (links for news tab)."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

# Add ml root so we can import src.features
_ml_root = Path(__file__).resolve().parent.parent.parent
if str(_ml_root) not in sys.path:
    sys.path.insert(0, str(_ml_root))

from src.features.stock_sentiment import get_sentiment_items_for_api

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/news/sentiment")
async def get_news_sentiment(
    symbol: str = Query(..., description="Stock ticker symbol"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
):
    """
    Return FinViz news items with article links and sentiment for the news tab.

    Items have id, title, url, source (FinViz), publishedAt, summary (sentiment).
    The edge news function can merge these with Alpaca news so the app shows
    linked articles from the same source we use for sentiment.
    """
    if not symbol or not symbol.strip():
        raise HTTPException(status_code=400, detail="symbol is required")
    ticker = symbol.strip().upper()
    try:
        items = get_sentiment_items_for_api(ticker, limit=limit)
        # Normalize for news API: publishedAt must be ISO string; url required for links
        for it in items:
            if not it.get("url"):
                it["url"] = "#"
        return {"symbol": ticker, "count": len(items), "items": items}
    except Exception as e:
        logger.exception("News sentiment fetch failed for %s", ticker)
        raise HTTPException(status_code=502, detail=f"Failed to fetch news: {e}") from e
