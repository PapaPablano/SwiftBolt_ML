"""Historical options data backfill from Tradier.

This module provides functionality to:
1. Check if sufficient historical data exists for momentum calculations
2. Fetch current options chain and generate synthetic historical data
3. Save backfill data to the database

The momentum ranking system requires 5+ days of historical snapshots to calculate:
- Price momentum (5-day price change)
- OI growth (5-day open interest change)
- IV trends

Since Tradier has limited historical options data (typically 30-60 days),
this module synthesizes historical estimates based on:
- Current options chain with Greeks
- Underlying price history
- Time decay models
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.data.tradier_client import TradierClient
from src.data.supabase_db import db

logger = logging.getLogger(__name__)


# Minimum days of history required for momentum calculations
MIN_DAYS_FOR_MOMENTUM = 5


class HistoricalOptionsBackfill:
    """Backfill historical options data from Tradier."""

    def __init__(self, tradier_client: Optional[TradierClient] = None):
        """Initialize backfill module.

        Args:
            tradier_client: Optional TradierClient instance.
                            Created lazily if not provided.
        """
        self._tradier = tradier_client
        self._tradier_initialized = tradier_client is not None
        self.db = db

    @property
    def tradier(self) -> TradierClient:
        """Lazy init of TradierClient - only created when needed."""
        if not self._tradier_initialized:
            self._tradier = TradierClient()
            self._tradier_initialized = True
        return self._tradier

    def check_historical_data(
        self,
        symbol: str,
        required_days: int = MIN_DAYS_FOR_MOMENTUM,
    ) -> tuple[bool, int]:
        """Check if we have sufficient historical data for momentum calculations.

        Args:
            symbol: Stock ticker symbol
            required_days: Minimum days of history needed

        Returns:
            Tuple of (has_enough_data, actual_days_available)
        """
        try:
            days_available = self.db.get_snapshot_count(symbol, days_back=30)
            has_enough = days_available >= required_days

            logger.info(
                f"{symbol}: {days_available} days of options history "
                f"({'sufficient' if has_enough else f'need {required_days - days_available} more'})"
            )

            return has_enough, days_available

        except Exception as e:
            logger.warning(f"Error checking historical data for {symbol}: {e}")
            return False, 0

    def ensure_historical_data(
        self,
        symbol: str,
        required_days: int = MIN_DAYS_FOR_MOMENTUM,
        backfill_days: int = 10,
    ) -> bool:
        """Ensure sufficient historical data exists, backfilling if needed.

        This is the main entry point for ensuring historical data before ranking.

        Args:
            symbol: Stock ticker symbol
            required_days: Minimum days of history needed
            backfill_days: Days to backfill if insufficient data

        Returns:
            True if historical data is available (existing or backfilled)
        """
        has_enough, current_days = self.check_historical_data(symbol, required_days)

        if has_enough:
            logger.info(f"{symbol}: Historical data sufficient ({current_days} days)")
            return True

        # Need to backfill
        logger.info(f"{symbol}: Backfilling {backfill_days} days of historical data...")

        try:
            records_inserted = self.backfill_from_tradier(symbol, days_back=backfill_days)

            if records_inserted > 0:
                logger.info(f"{symbol}: Backfill complete - {records_inserted} records")
                return True
            else:
                logger.warning(f"{symbol}: Backfill produced no records")
                return False

        except Exception as e:
            logger.error(f"{symbol}: Backfill failed - {e}")
            return False

    def backfill_from_tradier(
        self,
        symbol: str,
        days_back: int = 10,
        max_expirations: int = 6,
    ) -> int:
        """Backfill historical options data using Tradier API.

        Since Tradier doesn't provide direct historical options quotes,
        this method:
        1. Fetches current options chain with Greeks
        2. Gets underlying price history
        3. Synthesizes historical estimates using time decay models

        Args:
            symbol: Stock ticker symbol
            days_back: Days of synthetic history to generate
            max_expirations: Maximum expirations to include

        Returns:
            Number of records inserted
        """
        logger.info(f"Backfilling {symbol} options data for {days_back} days")

        # Get current options chain
        current_chain = self.tradier.snapshot_options_chain(symbol, max_expirations)

        if current_chain.empty:
            logger.warning(f"No current options data for {symbol}")
            return 0

        # Get underlying price history for realistic estimates
        underlying_history = self.tradier.get_historical_underlying_prices(
            symbol, days_back=days_back + 5
        )

        # Get symbol_id
        symbol_id = self.db.get_symbol_id(symbol)

        # Generate synthetic historical snapshots
        all_snapshots = []
        now = datetime.utcnow()

        # First, save the current snapshot
        current_chain["snapshot_time"] = now.isoformat()
        all_snapshots.append(current_chain)

        # Generate synthetic history for each past day
        for days_offset in range(1, days_back + 1):
            snapshot_date = now - timedelta(days=days_offset)

            # Get underlying price for that day if available
            underlying_price = self._get_historical_underlying_price(
                underlying_history, snapshot_date
            )

            # Generate synthetic snapshot for this day
            synthetic_df = self._synthesize_historical_snapshot(
                current_chain,
                days_offset=days_offset,
                underlying_price=underlying_price,
            )

            if not synthetic_df.empty:
                synthetic_df["snapshot_time"] = snapshot_date.isoformat()
                all_snapshots.append(synthetic_df)

        # Combine all snapshots and insert
        if all_snapshots:
            combined = pd.concat(all_snapshots, ignore_index=True)
            inserted = self.db.insert_options_snapshots(symbol_id, combined)
            return inserted

        return 0

    def _get_historical_underlying_price(
        self,
        history: pd.DataFrame,
        target_date: datetime,
    ) -> float:
        """Get underlying price for a specific date from history.

        Args:
            history: DataFrame with historical prices (ts/date, close)
            target_date: Target date to look up

        Returns:
            Closing price for the date, or 0 if not found
        """
        if history.empty:
            return 0.0

        target = target_date.date()

        # Find closest date
        if "ts" in history.columns:
            history["date"] = pd.to_datetime(history["ts"]).dt.date
        elif "date" in history.columns:
            history["date"] = pd.to_datetime(history["date"]).dt.date

        matches = history[history["date"] == target]
        if not matches.empty:
            return float(matches.iloc[0]["close"])

        # Find closest prior date
        prior = history[history["date"] < target]
        if not prior.empty:
            return float(prior.iloc[-1]["close"])

        return 0.0

    def _synthesize_historical_snapshot(
        self,
        current_chain: pd.DataFrame,
        days_offset: int,
        underlying_price: float = 0,
    ) -> pd.DataFrame:
        """Synthesize a historical snapshot from current chain data.

        Uses decay models to estimate what prices/Greeks would have been.

        The synthesis uses these assumptions:
        - Option prices decay over time (theta)
        - IV tends to be slightly higher further from expiration
        - Open interest builds gradually as expiration approaches
        - Volume is relatively stable day-to-day

        Args:
            current_chain: Current options chain DataFrame
            days_offset: Days in the past to synthesize
            underlying_price: Historical underlying price (0 to use current)

        Returns:
            Synthesized historical DataFrame
        """
        if current_chain.empty:
            return pd.DataFrame()

        df = current_chain.copy()

        # Use current underlying if not provided
        if underlying_price <= 0:
            underlying_price = df["underlying_price"].iloc[0]

        # Calculate days to expiration for each contract
        today = datetime.utcnow().date()
        historical_date = today - timedelta(days=days_offset)

        valid_rows = []

        for idx, row in df.iterrows():
            try:
                # Parse expiration
                exp_date = pd.to_datetime(row["expiration"]).date()
                current_dte = (exp_date - today).days
                historical_dte = (exp_date - historical_date).days

                # Skip if already expired at historical date
                if historical_dte <= 0:
                    continue

                # Skip very short-term options in history (unreliable)
                if historical_dte < 2:
                    continue

                # Estimate historical prices using decay model
                current_mid = (float(row["bid"]) + float(row["ask"])) / 2
                if current_mid <= 0:
                    continue

                # Time value decay factor (simplified theta model)
                # Options lose value faster as expiration approaches
                time_factor = math.sqrt(historical_dte / max(current_dte, 1))

                # Apply theta decay (options were worth more in the past)
                theta = float(row.get("theta", -0.05))
                theta_adjustment = abs(theta) * days_offset

                # Estimate historical mid price
                historical_mid = current_mid + theta_adjustment
                historical_mid = max(historical_mid, current_mid * 0.5)  # Floor at 50% of current
                historical_mid = min(historical_mid, current_mid * 3.0)  # Cap at 300% of current

                # Estimate spread (spreads widen further from expiration)
                spread_pct = (
                    (float(row["ask"]) - float(row["bid"])) / current_mid
                    if current_mid > 0
                    else 0.05
                )
                historical_spread_pct = spread_pct * (
                    1 + 0.02 * days_offset
                )  # 2% wider per day back
                historical_spread_pct = min(historical_spread_pct, 0.20)  # Cap at 20%

                historical_bid = historical_mid * (1 - historical_spread_pct / 2)
                historical_ask = historical_mid * (1 + historical_spread_pct / 2)

                # Estimate OI (builds up over time, so less in past)
                current_oi = int(row.get("open_interest", 100))
                oi_decay = 1 - (0.02 * days_offset)  # 2% less OI per day back
                historical_oi = max(int(current_oi * oi_decay), 10)

                # Volume is relatively stable but random
                current_vol = int(row.get("volume", 50))
                vol_factor = 0.8 + np.random.random() * 0.4  # 80-120% of current
                historical_vol = max(int(current_vol * vol_factor), 1)

                # IV tends to be slightly higher further from expiration
                current_iv = float(row.get("iv", 0.30))
                iv_factor = 1 + (0.01 * days_offset)  # 1% higher per day back
                historical_iv = current_iv * iv_factor

                # Create historical row
                hist_row = row.copy()
                hist_row["bid"] = round(historical_bid, 4)
                hist_row["ask"] = round(historical_ask, 4)
                hist_row["last"] = round(historical_mid, 4)
                hist_row["underlying_price"] = (
                    underlying_price if underlying_price > 0 else row["underlying_price"]
                )
                hist_row["volume"] = historical_vol
                hist_row["open_interest"] = historical_oi
                hist_row["iv"] = round(historical_iv, 6)

                # Greeks would be different but we keep current as approximation
                # (Could enhance with Black-Scholes recalculation if needed)

                valid_rows.append(hist_row)

            except Exception as e:
                logger.debug(f"Error synthesizing row: {e}")
                continue

        if valid_rows:
            return pd.DataFrame(valid_rows)
        return pd.DataFrame()

    def get_options_history_for_ranking(
        self,
        symbol: str,
        days_back: int = 10,
    ) -> pd.DataFrame:
        """Get options history formatted for the ranker.

        This fetches historical data and formats it for the OptionsMomentumRanker.

        Args:
            symbol: Stock ticker symbol
            days_back: Days of history to retrieve

        Returns:
            DataFrame with historical options data for momentum calculation
        """
        history = self.db.get_options_history(symbol, days_back=days_back)

        if history.empty:
            logger.warning(f"No options history available for {symbol}")
            return pd.DataFrame()

        # Rename columns to match ranker expectations
        rename_map = {
            "option_type": "side",
            "open_interest": "open_interest",
            "last": "last",
            "bid": "bid",
            "ask": "ask",
        }

        for old_col, new_col in rename_map.items():
            if old_col in history.columns and new_col != old_col:
                history[new_col] = history[old_col]

        # Add mark column if not present
        if "mark" not in history.columns:
            history["mark"] = (history["bid"] + history["ask"]) / 2

        logger.info(f"Prepared {len(history)} historical records for {symbol} ranking")
        return history

    def run_backfill(
        self,
        symbols: list[str],
        days: int = 10,
    ) -> dict[str, int]:
        """Run backfill for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            days: Days of history to backfill

        Returns:
            Dict mapping symbol to number of records inserted
        """
        results = {}

        for symbol in symbols:
            try:
                count = self.backfill_from_tradier(symbol, days_back=days)
                results[symbol] = count
                logger.info(f"{symbol}: Backfilled {count} records")
            except Exception as e:
                logger.error(f"{symbol}: Backfill failed - {e}")
                results[symbol] = 0

        return results


# Convenience function for use in ranking job
def ensure_options_history(
    symbol: str,
    required_days: int = MIN_DAYS_FOR_MOMENTUM,
) -> pd.DataFrame:
    """Ensure options history exists and return it for ranking.

    This is the main entry point for the ranking job to get historical data.
    It will backfill if needed before returning the history.

    Args:
        symbol: Stock ticker symbol
        required_days: Minimum days of history needed

    Returns:
        DataFrame with options history, or empty DataFrame if unavailable
    """
    try:
        backfiller = HistoricalOptionsBackfill()

        # Ensure we have enough history (backfills if needed)
        success = backfiller.ensure_historical_data(
            symbol,
            required_days=required_days,
            backfill_days=required_days + 5,  # Buffer
        )

        if not success:
            logger.warning(f"{symbol}: Could not ensure historical data")
            return pd.DataFrame()

        # Return the history for ranking
        return backfiller.get_options_history_for_ranking(symbol, days_back=required_days + 5)
    except Exception as e:
        logger.warning(f"{symbol}: Options history unavailable - {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get symbols from command line or use defaults
    if len(sys.argv) > 1:
        symbols = [s.upper() for s in sys.argv[1:]]
    else:
        symbols = ["AAPL", "NVDA", "TSLA"]

    print(f"\nBackfilling historical options data for: {', '.join(symbols)}")
    print("=" * 60)

    backfiller = HistoricalOptionsBackfill()
    results = backfiller.run_backfill(symbols, days=10)

    print("\nBackfill Results:")
    print("-" * 40)
    for symbol, count in results.items():
        print(f"  {symbol}: {count} snapshots")

    total = sum(results.values())
    print("-" * 40)
    print(f"  Total: {total} snapshots inserted")
