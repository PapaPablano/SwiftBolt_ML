"""Options ranking job that scores option contracts for key symbols."""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
import requests
import pandas as pd
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.models.options_ranker import OptionsRanker

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_options_from_api(symbol: str) -> dict:
    """
    Fetch options chain data from the /options-chain Edge Function.

    Args:
        symbol: Underlying ticker symbol

    Returns:
        Dictionary with options chain data
    """
    logger.info(f"Fetching options chain for {symbol} from Edge Function...")

    url = f"{settings.supabase_url}/functions/v1/options-chain"
    params = {"underlying": symbol}
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        logger.info(f"Fetched {len(data.get('calls', []))} calls and {len(data.get('puts', []))} puts")
        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch options chain for {symbol}: {e}")
        raise


def parse_options_chain(api_response: dict) -> pd.DataFrame:
    """Parse options chain API response into DataFrame with camelCase columns for ranker."""
    contracts = []

    for call in api_response.get("calls", []):
        contracts.append({
            "contract_symbol": call["symbol"],
            "strike": call["strike"],
            "expiration": call["expiration"],
            "side": "call",
            "bid": call.get("bid", 0),
            "ask": call.get("ask", 0),
            "mark": call.get("mark", (call.get("bid", 0) + call.get("ask", 0)) / 2),
            "last_price": call.get("last", 0),
            "volume": call.get("volume", 0),
            "openInterest": call.get("openInterest", 0),  # camelCase for ranker
            "impliedVolatility": call.get("impliedVolatility", 0),  # camelCase for ranker
            "delta": call.get("delta", 0),
            "gamma": call.get("gamma", 0),
            "theta": call.get("theta", 0),
            "vega": call.get("vega", 0),
            "rho": call.get("rho", 0),
        })

    for put in api_response.get("puts", []):
        contracts.append({
            "contract_symbol": put["symbol"],
            "strike": put["strike"],
            "expiration": put["expiration"],
            "side": "put",
            "bid": put.get("bid", 0),
            "ask": put.get("ask", 0),
            "mark": put.get("mark", (put.get("bid", 0) + put.get("ask", 0)) / 2),
            "last_price": put.get("last", 0),
            "volume": put.get("volume", 0),
            "openInterest": put.get("openInterest", 0),  # camelCase for ranker
            "impliedVolatility": put.get("impliedVolatility", 0),  # camelCase for ranker
            "delta": put.get("delta", 0),
            "gamma": put.get("gamma", 0),
            "theta": put.get("theta", 0),
            "vega": put.get("vega", 0),
            "rho": put.get("rho", 0),
        })

    return pd.DataFrame(contracts)


def calculate_days_to_expiry(expiration_ts: int) -> int:
    """Calculate days to expiration from Unix timestamp."""
    expiry_date = datetime.fromtimestamp(expiration_ts)
    today = datetime.now()
    return (expiry_date - today).days


def select_balanced_expiry_contracts(ranked_df: pd.DataFrame, total_contracts: int = 100) -> pd.DataFrame:
    """
    Select top contracts with balanced distribution across expiry ranges.

    Ensures we don't over-weight near-expiry ITM options by distributing
    selections across different time horizons:
    - Near-term (7-30 days): 30%
    - Mid-term (30-60 days): 40%
    - Long-term (60+ days): 30%

    Within each bucket, takes top contracts by ML score.

    Args:
        ranked_df: DataFrame of ranked options with ml_score and expiration columns
        total_contracts: Total number of contracts to select (default: 100)

    Returns:
        DataFrame with balanced selection of top contracts
    """
    if ranked_df.empty:
        return ranked_df

    # Add DTE column
    ranked_df = ranked_df.copy()
    ranked_df['dte'] = ranked_df['expiration'].apply(calculate_days_to_expiry)

    # Define expiry buckets
    near_term = ranked_df[ranked_df['dte'].between(7, 30)]
    mid_term = ranked_df[ranked_df['dte'].between(30, 60)]
    long_term = ranked_df[ranked_df['dte'] >= 60]
    very_short = ranked_df[ranked_df['dte'] < 7]  # Less than 1 week

    # Allocate contract counts
    near_count = int(total_contracts * 0.30)
    mid_count = int(total_contracts * 0.40)
    long_count = int(total_contracts * 0.25)
    very_short_count = int(total_contracts * 0.05)  # Only 5% for very short

    # Select top from each bucket
    selected_contracts = []

    if not very_short.empty:
        selected_contracts.append(very_short.nlargest(very_short_count, 'ml_score'))

    if not near_term.empty:
        selected_contracts.append(near_term.nlargest(near_count, 'ml_score'))

    if not mid_term.empty:
        selected_contracts.append(mid_term.nlargest(mid_count, 'ml_score'))

    if not long_term.empty:
        selected_contracts.append(long_term.nlargest(long_count, 'ml_score'))

    # If we didn't get enough contracts from buckets, backfill with top overall
    if selected_contracts:
        result = pd.concat(selected_contracts, ignore_index=True)
    else:
        result = pd.DataFrame()

    if len(result) < total_contracts:
        # Get remaining contracts from overall top-ranked
        remaining_count = total_contracts - len(result)
        excluded = ranked_df[~ranked_df.index.isin(result.index)]
        if not excluded.empty:
            backfill = excluded.nlargest(remaining_count, 'ml_score')
            result = pd.concat([result, backfill], ignore_index=True)

    # Sort by ml_score descending
    result = result.sort_values('ml_score', ascending=False)

    # Drop the temporary DTE column before returning
    result = result.drop(columns=['dte'])

    logger.info(
        f"Selected {len(result)} contracts: "
        f"{len(very_short.nlargest(very_short_count, 'ml_score'))} very short-term, "
        f"{len(near_term.nlargest(near_count, 'ml_score'))} near-term, "
        f"{len(mid_term.nlargest(mid_count, 'ml_score'))} mid-term, "
        f"{len(long_term.nlargest(long_count, 'ml_score'))} long-term"
    )

    return result


def save_rankings_to_db(symbol_id: str, ranked_df: pd.DataFrame) -> int:
    """Save ranked options to database."""
    saved_count = 0
    run_at = datetime.utcnow().isoformat()

    for _, row in ranked_df.iterrows():
        try:
            # Convert expiration timestamp to date string
            expiry_date = datetime.fromtimestamp(row["expiration"]).strftime("%Y-%m-%d")

            db.upsert_option_rank(
                underlying_symbol_id=symbol_id,
                contract_symbol=row["contract_symbol"],
                expiry=expiry_date,
                strike=float(row["strike"]),
                side=row["side"],
                ml_score=float(row["ml_score"]),
                implied_vol=float(row.get("impliedVolatility", 0)),  # Use camelCase
                delta=float(row.get("delta", 0)),
                gamma=float(row.get("gamma", 0)),
                theta=float(row.get("theta", 0)),
                vega=float(row.get("vega", 0)),
                rho=float(row.get("rho", 0)),
                bid=float(row.get("bid", 0)),
                ask=float(row.get("ask", 0)),
                mark=float(row.get("mark", 0)),
                last_price=float(row.get("last_price", 0)),
                volume=int(row.get("volume", 0)),
                open_interest=int(row.get("openInterest", 0)),  # Use camelCase
                run_at=run_at,
            )
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving rank for {row.get('contract_symbol')}: {e}")

    return saved_count


def process_symbol_options(symbol: str) -> None:
    """
    Process options for a single symbol: fetch data, rank contracts, save rankings.

    Args:
        symbol: Stock ticker symbol
    """
    logger.info(f"Processing options for {symbol}...")

    try:
        # Get symbol_id
        symbol_id = db.get_symbol_id(symbol)

        # Fetch recent OHLC data for the underlying
        df_ohlc = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=100)

        if df_ohlc.empty:
            logger.warning(f"No price data for {symbol}, skipping options ranking")
            return

        # Calculate underlying price and trend
        underlying_price = float(df_ohlc.iloc[-1]["close"])

        # Derive trend from recent price action (simplified)
        recent_prices = df_ohlc.tail(20)["close"]
        pct_change = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]

        if pct_change > 0.05:
            underlying_trend = "bullish"
        elif pct_change < -0.05:
            underlying_trend = "bearish"
        else:
            underlying_trend = "neutral"

        # Calculate historical volatility (20-day)
        returns = df_ohlc.tail(20)["close"].pct_change().dropna()
        historical_vol = returns.std() * (252 ** 0.5)  # Annualized

        logger.info(
            f"{symbol}: price=${underlying_price:.2f}, "
            f"trend={underlying_trend}, HV={historical_vol:.2%}"
        )

        # Fetch options chain from API
        api_response = fetch_options_from_api(symbol)
        options_df = parse_options_chain(api_response)

        if options_df.empty:
            logger.warning(f"No options contracts found for {symbol}")
            return

        logger.info(f"Parsed {len(options_df)} contracts for {symbol}")

        # Rank options using ML ranker
        ranker = OptionsRanker()
        ranked_df = ranker.rank_options(
            options_df,
            underlying_price,
            underlying_trend,
            historical_vol
        )

        logger.info(f"Ranked {len(ranked_df)} contracts for {symbol}")

        # Save top contracts with balanced expiry distribution
        top_ranked = select_balanced_expiry_contracts(ranked_df)
        saved_count = save_rankings_to_db(symbol_id, top_ranked)

        logger.info(f"✅ Saved {saved_count} ranked contracts for {symbol}")

    except Exception as e:
        logger.error(f"Error processing options for {symbol}: {e}", exc_info=True)


def main() -> None:
    """Main options ranking job entry point."""
    parser = argparse.ArgumentParser(description="Rank options contracts using ML")
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to process (e.g., AAPL). If not provided, processes all symbols from settings."
    )
    args = parser.parse_args()

    # Determine which symbols to process
    if args.symbol:
        symbols_to_process = [args.symbol.upper()]
    else:
        symbols_to_process = settings.symbols_to_process

    logger.info("=" * 80)
    logger.info("Starting Options Ranking Job")
    logger.info(f"Processing {len(symbols_to_process)} symbol(s): {', '.join(symbols_to_process)}")
    logger.info("=" * 80)

    symbols_processed = 0
    symbols_failed = 0

    for symbol in symbols_to_process:
        try:
            process_symbol_options(symbol)
            symbols_processed += 1
        except Exception as e:
            logger.error(f"Failed to process options for {symbol}: {e}")
            symbols_failed += 1

    logger.info("=" * 80)
    logger.info("Options Ranking Job Complete")
    logger.info(f"Processed: {symbols_processed}")
    logger.info(f"Failed: {symbols_failed}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
