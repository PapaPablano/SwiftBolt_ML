"""Supabase-based database access layer for SwiftBolt ML pipeline."""

import json
import logging
from typing import Any

import pandas as pd
from supabase import create_client, Client

from config.settings import settings

logger = logging.getLogger(__name__)


class SupabaseDatabase:
    """Supabase database client manager."""

    def __init__(self) -> None:
        """Initialize Supabase client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        logger.info("Supabase client initialized")

    def fetch_ohlc_bars(
        self,
        symbol: str,
        timeframe: str = "d1",
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars for a symbol from the database.

        Args:
            symbol: Stock ticker symbol
            timeframe: Timeframe (d1, h1, etc.)
            limit: Maximum number of bars to fetch (most recent)

        Returns:
            DataFrame with columns: ts, open, high, low, close, volume
        """
        try:
            # Get symbol_id
            symbol_response = (
                self.client.table("symbols")
                .select("id")
                .eq("ticker", symbol.upper())
                .single()
                .execute()
            )
            symbol_id = symbol_response.data["id"]

            # Fetch OHLC bars
            query = (
                self.client.table("ohlc_bars")
                .select("ts, open, high, low, close, volume")
                .eq("symbol_id", symbol_id)
                .eq("timeframe", timeframe)
                .order("ts", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            # Convert to DataFrame
            df = pd.DataFrame(response.data)

            if df.empty:
                logger.warning(f"No OHLC bars found for {symbol} ({timeframe})")
                return df

            # Convert timestamp to datetime and sort ascending
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.sort_values("ts").reset_index(drop=True)

            logger.info(f"Fetched {len(df)} bars for {symbol} ({timeframe})")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLC bars for {symbol}: {e}")
            raise

    def get_symbol_id(self, symbol: str) -> str:
        """
        Get the UUID for a symbol ticker.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Symbol UUID
        """
        try:
            response = (
                self.client.table("symbols")
                .select("id")
                .eq("ticker", symbol.upper())
                .single()
                .execute()
            )
            return response.data["id"]
        except Exception as e:
            logger.error(f"Error fetching symbol_id for {symbol}: {e}")
            raise

    def upsert_forecast(
        self,
        symbol_id: str,
        horizon: str,
        overall_label: str,
        confidence: float,
        points: list[dict[str, Any]],
    ) -> None:
        """
        Insert or update a forecast in the ml_forecasts table.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon (e.g., '1D', '1W')
            overall_label: Overall trend label (Bullish/Neutral/Bearish)
            confidence: Model confidence score (0-1)
            points: List of forecast points
        """
        try:
            # Check if forecast exists
            existing = (
                self.client.table("ml_forecasts")
                .select("id")
                .eq("symbol_id", symbol_id)
                .eq("horizon", horizon)
                .execute()
            )

            forecast_data = {
                "symbol_id": symbol_id,
                "horizon": horizon,
                "overall_label": overall_label,
                "confidence": confidence,
                "points": points,
            }

            if existing.data:
                # Delete existing forecast first to avoid trigger issues
                self.client.table("ml_forecasts").delete().eq("symbol_id", symbol_id).eq("horizon", horizon).execute()

            # Always insert (after deleting if it existed)
            response = (
                self.client.table("ml_forecasts")
                .insert(forecast_data)
                .execute()
            )

            logger.info(
                f"Saved forecast: {horizon} - {overall_label} "
                f"(confidence: {confidence:.2%})"
            )

        except Exception as e:
            logger.error(f"Error upserting forecast: {e}")
            raise

    def close(self) -> None:
        """Close the Supabase client (no-op for REST API)."""
        logger.info("Supabase client closed")


# Global instance
db = SupabaseDatabase()
