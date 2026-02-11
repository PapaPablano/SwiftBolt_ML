"""
PerplexityService: Lightweight async connector for Perplexity AI

- Fetches market intelligence (sentiment + brief analysis) for symbols
- Optional news search helper returning a pandas DataFrame

Design notes:
- Uses get_api_key('PERPLEXITY_API_KEY') with Streamlit secrets/env fallback
- Network errors/timeouts gracefully return neutral sentiment
- Async-first API with small sync wrappers for convenience

This module keeps external dependencies minimal and safe. If network access
or the API is unavailable, functions return sensible defaults so the app
remains responsive.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import aiohttp
except Exception:  # pragma: no cover - fallback if not installed
    aiohttp = None  # type: ignore

from main_production_system.core.secure_secrets import get_api_key


logger = logging.getLogger(__name__)


class PerplexityService:
    """
    Async client for Perplexity AI endpoints.

    Public methods:
      - get_market_intelligence(symbols: List[str]) -> Dict[str, Dict[str, Any]]
      - search_news(symbol: str, max_results: int = 3) -> pd.DataFrame
    """

    BASE_URL = "https://api.perplexity.ai"
    CHAT_ENDPOINT = "/chat/completions"

    def __init__(self, api_key: Optional[str] = None, request_timeout: int = 15) -> None:
        self.api_key = api_key or get_api_key("PERPLEXITY_API_KEY", default="")
        # Store aiohttp.ClientSession instance when available; keep typing generic to
        # avoid type resolution issues when aiohttp isn't installed.
        self._session: Optional[object] = None
        self._timeout = request_timeout

        if not self.api_key:
            logger.warning("Perplexity API key not configured; service will run in fallback mode.")

    # Async context manager helpers -------------------------------------------------
    async def __aenter__(self) -> "PerplexityService":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._close_session()

    # Internal session helpers ------------------------------------------------------
    async def _ensure_session(self) -> None:
        if self._session is None and aiohttp is not None:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _close_session(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()  # type: ignore[attr-defined]
            finally:
                self._session = None

    # Core API calls ----------------------------------------------------------------
    async def _chat(self, prompt: str, *, model: str = "sonar-small-online") -> Optional[Dict[str, Any]]:
        """
        Call Perplexity chat completion endpoint with a simple prompt.
        Returns parsed JSON or None on failure.
        """
        if aiohttp is None:
            logger.debug("aiohttp not installed; returning None from _chat")
            return None
        if not self.api_key:
            return None

        await self._ensure_session()
        assert self._session is not None

        url = self.BASE_URL + self.CHAT_ENDPOINT
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,  # online model with browsing capability (if available)
            "messages": [
                {"role": "system", "content": "You are a concise financial assistant."},
                {"role": "user", "content": prompt},
            ],
            # Keep it fast and cheap; no streaming
            "temperature": 0.2,
        }
        try:
            async with self._session.post(url, headers=headers, data=json.dumps(payload)) as resp:  # type: ignore[attr-defined]
                if resp.status != 200:
                    text = await resp.text()
                    logger.debug(f"Perplexity API non-200: {resp.status} {text[:200]}")
                    return None
                data = await resp.json()
                return data
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Perplexity API call failed: {e}")
            return None

    # Public methods ----------------------------------------------------------------
    async def get_market_intelligence(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        For each symbol, return a dictionary with keys:
          - sentiment: 'bullish' | 'bearish' | 'neutral'
          - confidence: float in [0, 1]
          - analysis: short text summary
        """
        results: Dict[str, Dict[str, Any]] = {}
        if not symbols:
            return results

        # Process sequentially with short timeouts; parallelization optional
        for sym in symbols:
            sym_u = str(sym).upper().strip()
            prompt = (
                f"For the stock {sym_u}, provide a one-line sentiment assessment as bullish, bearish, or neutral "
                f"with a confidence from 0.0 to 1.0 and a very brief reason (max 20 words). "
                f"Format: sentiment|confidence|reason"
            )

            default = {
                "sentiment": "neutral",
                "confidence": 0.5,
                "analysis": "No live data; default neutral sentiment.",
            }

            data = await self._chat(prompt)
            if not data:
                results[sym_u] = default
                continue

            try:
                content: str = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                parts = content.strip().split("|")
                if len(parts) >= 3:
                    raw_sent, raw_conf, reason = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
                    sentiment = "neutral"
                    if "bull" in raw_sent:
                        sentiment = "bullish"
                    elif "bear" in raw_sent:
                        sentiment = "bearish"
                    try:
                        conf = float(raw_conf)
                        conf = max(0.0, min(1.0, conf))
                    except Exception:
                        conf = 0.5
                    results[sym_u] = {
                        "sentiment": sentiment,
                        "confidence": conf,
                        "analysis": reason,
                    }
                else:
                    results[sym_u] = default
            except Exception:
                results[sym_u] = default

        return results

    async def search_news(self, symbol: str, max_results: int = 3) -> pd.DataFrame:
        """
        Attempt to retrieve recent news headlines. If API not available, returns empty DataFrame.

        Columns: title, source, url, published_date, summary
        """
        sym = str(symbol).upper().strip()
        # Heuristic prompt; some models can produce sources/links. If not, we return empty.
        prompt = (
            f"List the {max_results} most relevant and recent news headlines for {sym} with source and URL. "
            f"Format each as: title :: source :: url :: published_date (YYYY-MM-DD)."
        )

        data = await self._chat(prompt)
        rows: List[Dict[str, Any]] = []
        if not data:
            return pd.DataFrame(rows)
        try:
            content: str = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            # Parse lines formatted as requested
            for line in content.splitlines():
                parts = [p.strip() for p in line.split("::")]
                if len(parts) >= 4:
                    title, source, url, when = parts[:4]
                    rows.append(
                        {
                            "title": title,
                            "source": source,
                            "url": url,
                            "published_date": when,
                            "summary": None,
                        }
                    )
        except Exception:
            # Fallback to empty
            rows = []
        return pd.DataFrame(rows[:max_results])

    async def research_sector(self, sector: str, depth: str = "comprehensive") -> Dict[str, Any]:
        """Return a brief research summary for a sector."""
        prompt = (
            f"Provide a {depth} research summary for the {sector} sector in 5 bullet points."
        )
        data = await self._chat(prompt)
        if not data:
            return {"sector": sector, "summary": "No live data; default summary unavailable."}
        try:
            content: str = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {"sector": sector, "summary": content.strip()}
        except Exception:
            return {"sector": sector, "summary": "Summary parsing error."}

    # Synchronous wrappers ----------------------------------------------------------
    def get_market_intelligence_sync(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        return asyncio.run(self.get_market_intelligence(symbols))

    def search_news_sync(self, symbol: str, max_results: int = 3) -> pd.DataFrame:
        return asyncio.run(self.search_news(symbol, max_results=max_results))
