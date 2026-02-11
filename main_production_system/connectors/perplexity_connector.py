"""
PerplexityConnector: simple sync facade for PerplexityService

Provides a backwards-compatible interface used by API endpoints/tests.
"""
from __future__ import annotations

import pandas as pd

from main_production_system.data_sources.perplexity_service import PerplexityService


class PerplexityConnector:
    def __init__(self) -> None:
        self._svc = PerplexityService()

    def get_market_sentiment(self, symbol: str) -> dict:
        data = self._svc.get_market_intelligence_sync([symbol])
        sym = str(symbol).upper().strip()
        return {"symbol": sym, **data.get(sym, {})}

    def search_news(self, query: str, max_results: int = 10) -> pd.DataFrame:
        # Reuse symbol-oriented function for simplicity
        sym = str(query).upper().strip()
        return self._svc.search_news_sync(sym, max_results=max_results)
