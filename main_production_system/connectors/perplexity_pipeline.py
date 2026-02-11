"""
PerplexityPipeline: background monitoring utilities

Minimal implementation to support API background task endpoint.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from main_production_system.data_sources.perplexity_service import PerplexityService


logger = logging.getLogger(__name__)


class PerplexityPipeline:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    async def monitor_market_sentiment(self, symbols: List[str], duration_hours: int = 24, interval_seconds: int = 300) -> None:
        """
        Periodically fetch sentiment for symbols for a given duration.
        This demo implementation logs results; integrate with storage if needed.
        """
        end_time = datetime.utcnow() + timedelta(hours=max(1, int(duration_hours)))
        symbols_u = [s.upper().strip() for s in symbols or []]
        logger.info(f"[PerplexityPipeline] Starting monitor for {symbols_u} until {end_time.isoformat()}...")
        try:
            async with PerplexityService() as svc:
                while datetime.utcnow() < end_time:
                    try:
                        results = await svc.get_market_intelligence(symbols_u)
                        for sym, payload in results.items():
                            logger.info(
                                f"[PerplexityPipeline] {sym}: {payload.get('sentiment')} (conf={payload.get('confidence', 0.0):.2f})"
                            )
                    except Exception as e:
                        logger.warning(f"Monitor iteration failed: {e}")
                    await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("[PerplexityPipeline] Monitoring cancelled")
        except Exception as e:
            logger.warning(f"[PerplexityPipeline] Monitoring error: {e}")
        finally:
            logger.info("[PerplexityPipeline] Monitoring finished")
