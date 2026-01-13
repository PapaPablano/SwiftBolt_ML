"""
ML Forecast Service V2
Generates and persists forecasts to ohlc_bars_v2 with proper layer separation.

Features:
- Writes only to FUTURE dates (t+1 to t+10) with provider='ml_forecast'
- Includes confidence bands from model output
- Marks data as 'provisional' until verified
- Respects validation rules (won't write to historical/today)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..data.supabase_db import db

logger = logging.getLogger(__name__)


class ForecastServiceV2:
    """Service for generating and persisting ML forecasts to ohlc_bars_v2."""

    def __init__(self):
        self.db = db

    def generate_forecasts(
        self,
        symbol: str,
        base_price: float,
        horizon_days: int = 10,
        model_output: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Generate forecast data for future dates.

        Args:
            symbol: Stock ticker
            base_price: Latest close price to forecast from
            horizon_days: Number of days to forecast (max 10)
            model_output: Optional model predictions with confidence bands

        Returns:
            List of forecast dicts with ts, close, upper_band,
            lower_band, and confidence
        """
        if horizon_days > 10:
            logger.warning("Horizon %s exceeds max 10, capping", horizon_days)
            horizon_days = 10

        forecasts = []
        today = datetime.utcnow().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        for day in range(1, horizon_days + 1):
            target_date = today + timedelta(days=day)

            # If model output provided, use it
            if model_output and f"day_{day}" in model_output:
                pred = model_output[f"day_{day}"]
                forecast = {
                    "ts": target_date.isoformat() + "Z",
                    "close": pred.get("price", base_price),
                    "upper_band": pred.get("upper", base_price * 1.05),
                    "lower_band": pred.get("lower", base_price * 0.95),
                    "confidence": pred.get("confidence", 0.7),
                }
            else:
                # Placeholder: simple random walk with expanding bands
                drift = 0.001 * day
                volatility = 0.02 * (day**0.5)

                forecast = {
                    "ts": target_date.isoformat() + "Z",
                    "close": base_price * (1 + drift),
                    "upper_band": base_price * (1 + drift + volatility),
                    "lower_band": base_price * (1 + drift - volatility),
                    "confidence": max(0.5, 0.9 - (day * 0.04)),
                }

            forecasts.append(forecast)

        return forecasts

    def persist_forecasts(
        self,
        symbol: str,
        forecasts: List[Dict],
    ) -> Dict:
        """
        Persist forecasts to ohlc_bars_v2.

        Args:
            symbol: Stock ticker
            forecasts: List of forecast dicts from generate_forecasts()

        Returns:
            Dict with success status and stats
        """
        if not forecasts:
            return {"success": False, "error": "No forecasts to persist"}

        symbol_id = self.db.get_symbol_id(symbol)

        # Prepare rows for v2 table
        rows = []
        for forecast in forecasts:
            rows.append(
                {
                    "symbol_id": symbol_id,
                    "timeframe": "d1",
                    "ts": forecast["ts"],
                    "open": None,
                    "high": forecast["upper_band"],
                    "low": forecast["lower_band"],
                    "close": forecast["close"],
                    "volume": None,
                    "provider": "ml_forecast",
                    "is_intraday": False,
                    "is_forecast": True,
                    "data_status": "provisional",
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
                    "confidence_score": forecast["confidence"],
                    "upper_band": forecast["upper_band"],
                    "lower_band": forecast["lower_band"],
                }
            )

        try:
            # Upsert (will overwrite previous forecasts)
            self.db.client.table("ohlc_bars_v2").upsert(
                rows,
                on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
            ).execute()

            logger.info(f"✅ Persisted {len(rows)} forecasts for {symbol}")

            return {
                "success": True,
                "symbol": symbol,
                "forecasts_persisted": len(rows),
                "horizon_days": len(rows),
            }

        except Exception as e:
            logger.error("Error persisting forecasts for %s: %s", symbol, e)
            return {
                "success": False,
                "error": str(e),
            }

    def get_latest_close(self, symbol: str) -> Optional[float]:
        """
        Get the latest close price (from intraday if today, else historical).

        Args:
            symbol: Stock ticker

        Returns:
            Latest close price or None
        """
        try:
            symbol_id = self.db.get_symbol_id(symbol)
            today = datetime.utcnow().replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            # Try intraday first (today's data from Alpaca)
            response = (
                self.db.client.table("ohlc_bars_v2")
                .select("close")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", "d1")
                .eq("provider", "alpaca")
                .eq("is_intraday", True)
                .gte("ts", today.isoformat() + "Z")
                .order("ts", desc=True)
                .limit(1)
                .execute()
            )

            if response.data:
                return float(response.data[0]["close"])

            # Fall back to historical (Alpaca data)
            response = (
                self.db.client.table("ohlc_bars_v2")
                .select("close")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", "d1")
                .eq("provider", "alpaca")
                .eq("is_forecast", False)
                .order("ts", desc=True)
                .limit(1)
                .execute()
            )

            if response.data:
                return float(response.data[0]["close"])

            return None

        except Exception as e:
            logger.error("Error getting latest close for %s: %s", symbol, e)
            return None

    def update_forecasts(
        self,
        symbol: str,
        model_output: Optional[Dict] = None,
        horizon_days: int = 10,
    ) -> Dict:
        """
        Generate and persist forecasts for a symbol.

        Args:
            symbol: Stock ticker
            model_output: Optional model predictions
            horizon_days: Number of days to forecast

        Returns:
            Dict with success status and stats
        """
        # Get latest close price
        base_price = self.get_latest_close(symbol)
        if not base_price:
            return {
                "success": False,
                "error": f"No base price found for {symbol}",
            }

        # Generate forecasts
        forecasts = self.generate_forecasts(
            symbol=symbol,
            base_price=base_price,
            horizon_days=horizon_days,
            model_output=model_output,
        )

        # Persist to database
        result = self.persist_forecasts(symbol, forecasts)

        return result

    def update_batch(
        self,
        symbols: List[str],
        horizon_days: int = 10,
    ) -> Dict:
        """
        Update forecasts for multiple symbols.

        Args:
            symbols: List of stock tickers
            horizon_days: Number of days to forecast

        Returns:
            Dict with successful and failed symbols
        """
        successful = []
        failed = []

        for symbol in symbols:
            logger.info(f"Updating forecasts for {symbol}")

            result = self.update_forecasts(
                symbol=symbol,
                horizon_days=horizon_days,
            )

            if result["success"]:
                successful.append(symbol)
            else:
                failed.append(
                    {
                        "symbol": symbol,
                        "error": result.get("error", "Unknown error"),
                    }
                )

        logger.info(
            "Forecast update complete: %s successful, %s failed",
            len(successful),
            len(failed),
        )

        return {
            "successful": successful,
            "failed": failed,
            "total": len(symbols),
        }


def main():
    """CLI entry point for forecast updates."""
    import argparse

    parser = argparse.ArgumentParser(description="Update ML forecasts in ohlc_bars_v2")
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to update",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Multiple symbols to update",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all watchlist symbols",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=10,
        help="Forecast horizon in days (default: 10)",
    )

    args = parser.parse_args()

    service = ForecastServiceV2()

    # Determine symbols
    symbols = []
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    elif args.all:
        try:
            response = db.client.rpc(
                "get_all_watchlist_symbols",
                {"p_limit": 200},
            ).execute()
            symbols = [row["ticker"] for row in response.data]
        except Exception as e:
            logger.error(f"Error fetching watchlist: {e}")
            return 1
    else:
        logger.error("Must specify --symbol, --symbols, or --all")
        return 1

    logger.info(f"Updating forecasts for {len(symbols)} symbols")

    result = service.update_batch(symbols, horizon_days=args.horizon)

    logger.info(f"\n{'='*60}")
    logger.info("FORECAST UPDATE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Successful: {len(result['successful'])}")
    logger.info(f"❌ Failed: {len(result['failed'])}")

    if result["failed"]:
        logger.info("\nFailed symbols:")
        for item in result["failed"]:
            logger.info(f"  - {item['symbol']}: {item['error']}")

    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
