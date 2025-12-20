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
            settings.supabase_key,
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
        supertrend_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Insert or update a forecast in the ml_forecasts table.

        Args:
            symbol_id: UUID of the symbol
            horizon: Forecast horizon (e.g., '1D', '1W')
            overall_label: Overall trend label (Bullish/Neutral/Bearish)
            confidence: Model confidence score (0-1)
            points: List of forecast points
            supertrend_data: Optional SuperTrend AI data dict
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

            # Add SuperTrend AI data if available
            if supertrend_data:
                forecast_data.update({
                    "supertrend_factor": supertrend_data.get("supertrend_factor"),
                    "supertrend_performance": supertrend_data.get(
                        "supertrend_performance"
                    ),
                    "supertrend_signal": supertrend_data.get("supertrend_signal"),
                    "trend_label": supertrend_data.get("trend_label"),
                    "trend_confidence": supertrend_data.get("trend_confidence"),
                    "stop_level": supertrend_data.get("stop_level"),
                    "trend_duration_bars": supertrend_data.get(
                        "trend_duration_bars"
                    ),
                })

            if existing.data:
                # Delete existing forecast first to avoid trigger issues
                (
                    self.client.table("ml_forecasts")
                    .delete()
                    .eq("symbol_id", symbol_id)
                    .eq("horizon", horizon)
                    .execute()
                )

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

    def upsert_supertrend_signals(
        self,
        symbol: str,
        signals: list[dict[str, Any]],
    ) -> None:
        """
        Insert SuperTrend signals into the supertrend_signals table.

        Args:
            symbol: Stock ticker symbol
            signals: List of signal dictionaries from SuperTrendAI
        """
        if not signals:
            return

        try:
            for signal in signals:
                signal_data = {
                    "symbol": symbol.upper(),
                    "signal_date": signal["date"],
                    "signal_type": signal["type"],
                    "entry_price": signal["price"],
                    "stop_level": signal["stop_level"],
                    "target_price": signal.get("target_price"),
                    "confidence": signal.get("confidence"),
                    "atr_at_signal": signal.get("atr_at_signal"),
                    "risk_amount": signal.get("risk_amount"),
                    "reward_amount": signal.get("reward_amount"),
                    "outcome": "OPEN",
                }

                # Upsert (insert or update on conflict)
                self.client.table("supertrend_signals").upsert(
                    signal_data,
                    on_conflict="symbol,signal_date,signal_type",
                ).execute()

            logger.info(f"Saved {len(signals)} SuperTrend signals for {symbol}")

        except Exception as e:
            logger.warning(f"Error upserting SuperTrend signals for {symbol}: {e}")

    def upsert_option_rank(
        self,
        underlying_symbol_id: str,
        contract_symbol: str,
        expiry: str,
        strike: float,
        side: str,
        ml_score: float,
        implied_vol: float,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
        rho: float,
        bid: float,
        ask: float,
        mark: float,
        last_price: float,
        volume: int,
        open_interest: int,
        run_at: str,
    ) -> None:
        """
        Insert or update an option rank in the options_ranks table.

        Args:
            underlying_symbol_id: UUID of the underlying symbol
            contract_symbol: Options contract symbol
            expiry: Expiration date (YYYY-MM-DD)
            strike: Strike price
            side: "call" or "put"
            ml_score: ML ranking score (0-1)
            implied_vol: Implied volatility
            delta: Option delta
            gamma: Option gamma
            theta: Option theta
            vega: Option vega
            rho: Option rho
            bid: Bid price
            ask: Ask price
            mark: Mark price
            last_price: Last traded price
            volume: Volume
            open_interest: Open interest
            run_at: Timestamp when ranking was generated
        """
        try:
            rank_data = {
                "underlying_symbol_id": underlying_symbol_id,
                "contract_symbol": contract_symbol,
                "expiry": expiry,
                "strike": strike,
                "side": side,
                "ml_score": ml_score,
                "implied_vol": implied_vol,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "bid": bid,
                "ask": ask,
                "mark": mark,
                "last_price": last_price,
                "volume": volume,
                "open_interest": open_interest,
                "run_at": run_at,
            }

            # Delete existing rank for this contract if it exists
            self.client.table("options_ranks").delete().eq("contract_symbol", contract_symbol).execute()

            # Insert new rank
            response = (
                self.client.table("options_ranks")
                .insert(rank_data)
                .execute()
            )

            logger.debug(f"Saved rank for {contract_symbol} (score: {ml_score:.3f})")

        except Exception as e:
            logger.error(f"Error upserting option rank for {contract_symbol}: {e}")
            raise

    def close(self) -> None:
        """Close the Supabase client (no-op for REST API)."""
        logger.info("Supabase client closed")


# Global instance
db = SupabaseDatabase()
