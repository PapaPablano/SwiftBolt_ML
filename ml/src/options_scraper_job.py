"""Options Chain Scraper Job.

Fetches options chains from Tradier and saves to Supabase for ML training.
Run this daily to build historical options data.

Usage:
    # Fetch options for default watchlist
    python -m src.options_scraper_job

    # Fetch for specific symbols
    python -m src.options_scraper_job --symbols AAPL,SPY,NVDA

    # Fetch with more expirations
    python -m src.options_scraper_job --max-expirations 6
"""

import argparse
import logging
from datetime import datetime, date, timezone
import math

import pandas as pd

from config.settings import settings
from src.data.tradier_client import TradierClient
from src.data.supabase_db import SupabaseDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OptionsScraperJob:
    """Job to scrape options chains and save to database."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        max_expirations: int = 4,
    ):
        """Initialize scraper job.

        Args:
            symbols: List of underlying symbols to scrape
            max_expirations: Max expirations per symbol to fetch
        """
        self.symbols = symbols or settings.symbols_to_process
        self.max_expirations = max_expirations
        self.tradier = TradierClient()
        self.db = SupabaseDatabase()

        logger.info(f"Options scraper initialized for {len(self.symbols)} symbols")

    def fetch_and_save_chain(self, symbol: str) -> int:
        """Fetch options chain for a symbol and save to database.

        Args:
            symbol: Underlying stock symbol

        Returns:
            Number of options saved
        """
        logger.info(f"Fetching options chain for {symbol}")

        try:
            # Get underlying quote for current price
            quote = self.tradier.get_quote(symbol)
            underlying_price = quote.get("last", quote.get("close", 0))

            # Get options chains
            chain_df = self.tradier.get_all_chains(
                symbol,
                max_expirations=self.max_expirations,
                greeks=True,
            )

            if chain_df.empty:
                logger.warning(f"No options data for {symbol}")
                return 0

            # Add underlying price
            chain_df["underlying_price"] = underlying_price

            # Save to database
            saved = self._save_options_to_db(chain_df, symbol)

            logger.info(f"Saved {saved} options for {symbol}")
            return saved

        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            return 0

    def _save_options_to_db(self, df: pd.DataFrame, symbol: str) -> int:
        """Save options data to Supabase.

        Args:
            df: Options chain DataFrame
            symbol: Underlying symbol

        Returns:
            Number of records saved
        """
        # Get symbol ID
        try:
            symbol_id = self.db.get_symbol_id(symbol)
        except Exception:
            logger.warning(f"Symbol {symbol} not in database, skipping save")
            return 0

        records = []
        snapshot_time = datetime.now(timezone.utc).isoformat()

        def safe_float(val, default=0.0):
            """Convert to float, replacing NaN/None with default."""
            if val is None:
                return default
            try:
                f = float(val)
                return default if math.isnan(f) else f
            except (ValueError, TypeError):
                return default

        def safe_int(val, default=0):
            """Convert to int, replacing NaN/None with default."""
            if val is None:
                return default
            try:
                f = float(val)
                return default if math.isnan(f) else int(f)
            except (ValueError, TypeError):
                return default

        for _, row in df.iterrows():
            record = {
                "underlying_symbol_id": symbol_id,
                "contract_symbol": row.get("symbol", ""),
                "option_type": row.get("option_type", ""),
                "strike": safe_float(row.get("strike", 0)),
                "expiration": row.get("expiration_date", ""),
                "bid": safe_float(row.get("bid")),
                "ask": safe_float(row.get("ask")),
                "last": safe_float(row.get("last")),
                "volume": safe_int(row.get("volume")),
                "open_interest": safe_int(row.get("open_interest")),
                "underlying_price": safe_float(row.get("underlying_price")),
                "snapshot_time": snapshot_time,
                # Greeks
                "delta": safe_float(row.get("greek_delta")),
                "gamma": safe_float(row.get("greek_gamma")),
                "theta": safe_float(row.get("greek_theta")),
                "vega": safe_float(row.get("greek_vega")),
                "rho": safe_float(row.get("greek_rho")),
                "iv": safe_float(row.get("greek_mid_iv")),
            }
            records.append(record)

        if not records:
            return 0

        # Upsert in batches
        batch_size = 500
        total_saved = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                self.db.client.table("options_snapshots").upsert(
                    batch,
                    on_conflict="contract_symbol,snapshot_time",
                ).execute()
                total_saved += len(batch)
            except Exception as e:
                logger.error(f"Failed to save batch: {e}")

        return total_saved

    def run(self) -> dict[str, int]:
        """Run the scraper for all symbols.

        Returns:
            Dict mapping symbol -> options count saved
        """
        results = {}

        for symbol in self.symbols:
            try:
                count = self.fetch_and_save_chain(symbol)
                results[symbol] = count
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                results[symbol] = 0

        # Summary
        total = sum(results.values())
        logger.info(f"Scraper complete: {total} total options saved")

        return results

    def export_to_csv(self, output_dir: str = "data/options_export") -> None:
        """Export options chains to CSV files for analysis.

        Args:
            output_dir: Output directory for CSV files
        """
        from pathlib import Path

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for symbol in self.symbols:
            try:
                chain_df = self.tradier.get_all_chains(
                    symbol,
                    max_expirations=self.max_expirations,
                    greeks=True,
                )

                if not chain_df.empty:
                    # Get underlying price
                    quote = self.tradier.get_quote(symbol)
                    chain_df["underlying_price"] = quote.get("last", 0)

                    # Save to CSV
                    filename = f"{symbol}_options_{date.today()}.csv"
                    chain_df.to_csv(output_path / filename, index=False)
                    logger.info(f"Exported {len(chain_df)} options to {filename}")

            except Exception as e:
                logger.error(f"Failed to export {symbol}: {e}")


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Scrape options chains from Tradier")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols (default: from settings)",
    )
    parser.add_argument(
        "--max-expirations",
        type=int,
        default=4,
        help="Max expirations per symbol (default: 4)",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export to CSV instead of saving to database",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/options_export",
        help="Output directory for CSV export",
    )

    args = parser.parse_args()

    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]

    job = OptionsScraperJob(
        symbols=symbols,
        max_expirations=args.max_expirations,
    )

    if args.export_csv:
        job.export_to_csv(args.output_dir)
    else:
        results = job.run()
        print("\nResults:")
        for symbol, count in results.items():
            print(f"  {symbol}: {count} options")


if __name__ == "__main__":
    main()
