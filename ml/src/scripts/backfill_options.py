"""
Nightly Options Chain Backfill Script.

This script fetches options chain data for all watchlisted symbols,
stores snapshots in options_chain_snapshots, and updates options_ranks.

Features:
- Server-side watchlist: fetches symbols from all user watchlists (up to 200)
- Fetches ALL expirations for each symbol (nightly comprehensive update)
- Batch inserts (1000 records/batch) for fast database writes
- No slow single-record fallback - retry batch once, then skip
- Stores raw snapshot data for historical analysis
- Updates ML-scored options_ranks table
- Rate limiting to respect API quotas
- Retry with exponential backoff for transient errors

Usage:
    python src/scripts/backfill_options.py --all
        # Process all watchlist symbols
    python src/scripts/backfill_options.py --symbol AAPL
        # Single symbol
    python src/scripts/backfill_options.py --symbols AAPL TSLA NVDA
        # Multiple symbols
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.models.options_momentum_ranker import (  # noqa: E402
    IVStatistics,
    OptionsMomentumRanker,
)
from src.options_historical_backfill import ensure_options_history  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validate required environment variables at startup
logger.info(
    f"Supabase URL: {settings.supabase_url[:30]}..."
    if settings.supabase_url
    else "Supabase URL: NOT SET"
)
logger.info(
    "Supabase Key: %s",
    (f"SET ({len(settings.supabase_key)} chars)" if settings.supabase_key else "NOT SET"),
)
if not settings.supabase_url or not settings.supabase_key:
    logger.error("Missing required Supabase credentials!")
    sys.exit(1)

# Validate secrets don't contain invalid characters that would cause HTTP header errors
def validate_secret(name: str, value: str | None) -> None:
    """Validate that a secret value is suitable for use in HTTP headers."""
    if value is None:
        return
    if "\n" in value or "\r" in value:
        logger.error(f"{name} contains newline characters - this will cause HTTP header errors!")
        sys.exit(1)
    if not value.strip():
        logger.error(f"{name} is empty or whitespace-only!")
        sys.exit(1)

validate_secret("SUPABASE_URL", settings.supabase_url)
validate_secret("SUPABASE_KEY", settings.supabase_key)

# Fallback symbols if database watchlist is empty
DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "META",
    "SPY",
    "QQQ",
    "CRWD",
    "PLTR",
    "AMD",
    "NFLX",
    "DIS",
]


def determine_trend(df_ohlc: pd.DataFrame) -> str:
    if df_ohlc is None or df_ohlc.empty or len(df_ohlc) < 20:
        return "neutral"

    close = df_ohlc["close"]
    sma_10 = close.tail(10).mean()
    sma_20 = close.tail(20).mean()
    current = close.iloc[-1]

    if current > sma_10 > sma_20:
        return "bullish"
    if current < sma_10 < sma_20:
        return "bearish"
    return "neutral"


def fetch_iv_stats(symbol_id: str) -> IVStatistics | None:
    try:
        result = db.client.rpc(
            "calculate_iv_rank",
            {"p_symbol_id": symbol_id},
        ).execute()
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return IVStatistics(
                iv_current=row.get("iv_current", 0.3),
                iv_high=row.get("iv_52_high", 0.5),
                iv_low=row.get("iv_52_low", 0.2),
                iv_median=row.get("iv_52_high", 0.35) * 0.7,
            )
    except Exception as e:
        logger.warning(f"Could not fetch IV stats: {e}")
    return None


def fetch_previous_rankings(symbol_id: str, ranking_mode: str) -> pd.DataFrame:
    try:
        latest = (
            db.client.table("options_ranks")
            .select("run_at")
            .eq("underlying_symbol_id", symbol_id)
            .eq("ranking_mode", ranking_mode)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )

        if not latest.data:
            return pd.DataFrame()

        latest_run_at = latest.data[0]["run_at"]
        rows = (
            db.client.table("options_ranks")
            .select(
                "contract_symbol,strike,side,composite_rank,momentum_score,"
                "value_score,greeks_score,ranking_mode"
            )
            .eq("underlying_symbol_id", symbol_id)
            .eq("ranking_mode", ranking_mode)
            .eq("run_at", latest_run_at)
            .execute()
        )
        df = pd.DataFrame(rows.data or [])
        if df.empty:
            return df

        for col in [
            "composite_rank",
            "momentum_score",
            "value_score",
            "greeks_score",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["momentum_score", "composite_rank"])
        return df
    except Exception as e:
        logger.warning(f"Could not fetch previous rankings: {e}")
        return pd.DataFrame()


# Rate limiting configuration
RATE_LIMIT_DELAY = 2.0  # Seconds between API calls
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
RETRYABLE_STATUS_CODES = {502, 503, 504}

# Batch insert configuration
# Insert this many records at once (Supabase/Postgres handles this well)
BATCH_SIZE = 1000


def get_watchlist_symbols_from_db(limit: int = 200) -> List[str]:
    """
    Fetch all unique symbols from user watchlists in the database.
    Falls back to DEFAULT_SYMBOLS if no watchlist symbols found.
    """
    try:
        response = db.client.rpc("get_all_watchlist_symbols", {"p_limit": limit}).execute()

        if response.data:
            symbols = [row["ticker"] for row in response.data]
            logger.info(f"Fetched {len(symbols)} symbols from user watchlists")
            return symbols
        else:
            logger.warning("No symbols found in user watchlists, using defaults")
            return DEFAULT_SYMBOLS

    except Exception as e:
        logger.warning(f"Could not fetch watchlist symbols from DB: {e}")
        logger.info("Falling back to default symbol list")
        return DEFAULT_SYMBOLS


def fetch_options_chain(underlying: str, expiration: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch options chain data from the /options-chain Edge Function.
    Includes retry logic with exponential backoff for transient errors.
    """
    url = f"{settings.supabase_url}/functions/v1/options-chain"
    params = {"underlying": underlying}
    if expiration:
        params["expiration"] = str(expiration)

    headers = {
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
    }

    logger.info(f"Fetching options chain for {underlying}...")

    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            calls_count = len(data.get("calls", []))
            puts_count = len(data.get("puts", []))
            expirations_count = len(data.get("expirations", []))
            logger.info(
                f"Fetched {calls_count} calls, {puts_count} puts, "
                f"{expirations_count} expirations for {underlying}"
            )

            return data
        except requests.exceptions.HTTPError as e:
            last_exception = e
            status_code = e.response.status_code if e.response is not None else 0

            if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Transient error (%s) for %s, retrying in %.1fs " "(attempt %s/%s)...",
                    status_code,
                    underlying,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            else:
                logger.error(f"Failed to fetch options chain for {underlying}: {e}")
                raise
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Request error for %s, retrying in %.1fs " "(attempt %s/%s)...",
                    underlying,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            else:
                logger.error(f"Failed to fetch options chain for {underlying}: {e}")
                raise

    raise last_exception or Exception(f"Failed to fetch options chain for {underlying}")


def persist_options_snapshot(
    underlying: str,
    calls: List[Dict],
    puts: List[Dict],
    snapshot_date: date,
    ml_scores: Optional[Dict[str, float]] = None,
) -> tuple[int, int]:
    """
    Persist options chain data to the options_chain_snapshots table.
    Uses batch inserts for performance.

    Args:
        underlying: Underlying symbol
        calls: List of call contracts
        puts: List of put contracts
        snapshot_date: Date of snapshot
        ml_scores: Optional dict mapping contract key to ml_score
                   Key format: "{expiry}_{strike}_{side}"

    Returns (inserted_count, skipped_count).
    """
    try:
        symbol_id = db.get_symbol_id(underlying)
    except Exception as e:
        logger.error(f"Could not get symbol_id for {underlying}: {e}")
        return 0, 0

    inserted = 0
    skipped = 0

    all_contracts = [(contract, "call") for contract in calls] + [
        (contract, "put") for contract in puts
    ]

    # Build batch of records
    batch = []
    for contract, side in all_contracts:
        try:
            expiration_ts = contract.get("expiration", 0)
            expiry_date = datetime.fromtimestamp(expiration_ts).date()

            # Build contract key for ml_score lookup
            strike_val = float(contract.get("strike", 0))
            contract_key = f"{expiry_date.isoformat()}_{strike_val}_{side}"

            # Get ml_score if available
            ml_score = None
            if ml_scores and contract_key in ml_scores:
                ml_score = ml_scores[contract_key]

            snapshot_data = {
                "underlying_symbol_id": symbol_id,
                "expiry": expiry_date.isoformat(),
                "strike": strike_val,
                "side": side,
                "bid": float(contract.get("bid", 0)),
                "ask": float(contract.get("ask", 0)),
                "mark": float(contract.get("mark", 0)),
                "last_price": float(contract.get("last", 0)),
                "volume": int(contract.get("volume", 0)),
                "open_interest": int(contract.get("openInterest", 0)),
                "implied_vol": (
                    float(contract.get("impliedVolatility", 0))
                    if contract.get("impliedVolatility")
                    else None
                ),
                "delta": (float(contract.get("delta", 0)) if contract.get("delta") else None),
                "gamma": (float(contract.get("gamma", 0)) if contract.get("gamma") else None),
                "theta": (float(contract.get("theta", 0)) if contract.get("theta") else None),
                "vega": (float(contract.get("vega", 0)) if contract.get("vega") else None),
                "rho": (float(contract.get("rho", 0)) if contract.get("rho") else None),
                "snapshot_date": snapshot_date.isoformat(),
                "ml_score": ml_score,
            }
            batch.append(snapshot_data)
        except Exception as e:
            logger.debug("Skipped contract: %s", e)
            skipped += 1

    # Insert in batches - no slow fallback, just retry once and move on
    total_batches = (len(batch) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num, i in enumerate(range(0, len(batch), BATCH_SIZE), 1):
        chunk = batch[i : i + BATCH_SIZE]
        for attempt in range(2):  # Max 2 attempts per batch
            try:
                db.client.table("options_chain_snapshots").upsert(
                    chunk,
                    on_conflict=("underlying_symbol_id,expiry,strike,side," "snapshot_date"),
                ).execute()
                inserted += len(chunk)
                break  # Success, move to next batch
            except Exception as e:
                if attempt == 0:
                    logger.debug(
                        "Batch %s/%s failed, retrying: %s",
                        batch_num,
                        total_batches,
                        e,
                    )
                    time.sleep(1)  # Brief pause before retry
                else:
                    logger.warning(
                        "Batch %s/%s failed after retry, skipping %s " "records: %s",
                        batch_num,
                        total_batches,
                        len(chunk),
                        e,
                    )
                    skipped += len(chunk)

    logger.info(
        "Persisted %s snapshot contracts for %s (%s skipped)",
        inserted,
        underlying,
        skipped,
    )
    return inserted, skipped


def calculate_ml_scores(underlying: str, calls: List[Dict], puts: List[Dict]) -> Dict[str, float]:
    """
    Calculate ML scores for all contracts.

    Returns dict mapping contract key to ml_score.
    Key format: "{expiry}_{strike}_{side}"
    """
    ml_scores = {}

    all_contracts = [(contract, "call") for contract in calls] + [
        (contract, "put") for contract in puts
    ]

    for contract, side in all_contracts:
        try:
            expiration_ts = contract.get("expiration", 0)
            expiry_date = datetime.fromtimestamp(expiration_ts).date()
            strike = float(contract.get("strike", 0))

            # Simple ML score heuristic (placeholder for actual ML model)
            volume = int(contract.get("volume", 0))
            oi = int(contract.get("openInterest", 0))
            delta = abs(float(contract.get("delta", 0)) if contract.get("delta") else 0)
            iv = (
                float(contract.get("impliedVolatility", 0))
                if contract.get("impliedVolatility")
                else 0
            )

            # Score components (0-1 range each)
            volume_score = min(volume / 1000, 1.0)
            oi_score = min(oi / 5000, 1.0)
            delta_score = 1.0 - abs(delta - 0.5) * 2
            iv_score = min(iv / 1.0, 1.0)

            ml_score = volume_score * 0.25 + oi_score * 0.25 + delta_score * 0.3 + iv_score * 0.2

            # Build key
            contract_key = f"{expiry_date.isoformat()}_{strike}_{side}"
            ml_scores[contract_key] = round(ml_score, 4)
        except Exception:
            pass  # Skip contracts that fail

    return ml_scores


def update_options_ranks(underlying: str, calls: List[Dict], puts: List[Dict]) -> int:
    """
    Update the options_ranks table with Momentum Framework scores.
    Uses batch inserts for performance.
    Returns count of updated ranks.
    """
    try:
        symbol_id = db.get_symbol_id(underlying)
    except Exception as e:
        logger.error(f"Could not get symbol_id for {underlying}: {e}")
        return 0

    updated = 0
    skipped = 0
    run_at = datetime.utcnow().isoformat()

    def _float_or_none(v: Any) -> float | None:
        if v is None:
            return None
        try:
            fv = float(v)
        except Exception:
            return None
        if not np.isfinite(fv):
            return None
        return fv

    def _float_or_zero(v: Any) -> float:
        fv = _float_or_none(v)
        return 0.0 if fv is None else fv

    def _int_or_zero(v: Any) -> int:
        if v is None:
            return 0
        try:
            iv = int(v)
        except Exception:
            try:
                fv = float(v)
            except Exception:
                return 0
            if not np.isfinite(fv):
                return 0
            return int(fv)
        return iv

    contracts: list[dict[str, Any]] = []
    for contract in calls:
        contracts.append(
            {
                "contract_symbol": contract.get("symbol", ""),
                "strike": float(contract.get("strike") or 0),
                "expiration": int(contract.get("expiration") or 0),
                "side": "call",
                "bid": float(contract.get("bid") or 0),
                "ask": float(contract.get("ask") or 0),
                "mark": float(contract.get("mark") or 0),
                "last_price": float(contract.get("last") or 0),
                "volume": int(contract.get("volume", 0)),
                "openInterest": int(contract.get("openInterest", 0)),
                "impliedVolatility": float(contract.get("impliedVolatility") or 0),
                "delta": float(contract.get("delta") or 0),
                "gamma": float(contract.get("gamma") or 0),
                "theta": float(contract.get("theta") or 0),
                "vega": float(contract.get("vega") or 0),
                "rho": float(contract.get("rho") or 0),
            }
        )
    for contract in puts:
        contracts.append(
            {
                "contract_symbol": contract.get("symbol", ""),
                "strike": float(contract.get("strike") or 0),
                "expiration": int(contract.get("expiration") or 0),
                "side": "put",
                "bid": float(contract.get("bid") or 0),
                "ask": float(contract.get("ask") or 0),
                "mark": float(contract.get("mark") or 0),
                "last_price": float(contract.get("last") or 0),
                "volume": int(contract.get("volume", 0)),
                "openInterest": int(contract.get("openInterest", 0)),
                "impliedVolatility": float(contract.get("impliedVolatility") or 0),
                "delta": float(contract.get("delta") or 0),
                "gamma": float(contract.get("gamma") or 0),
                "theta": float(contract.get("theta") or 0),
                "vega": float(contract.get("vega") or 0),
                "rho": float(contract.get("rho") or 0),
            }
        )

    df = pd.DataFrame(contracts)
    if df.empty:
        return 0

    # Filter invalid contracts (these can cause duplicate keys / bad dates)
    if "contract_symbol" in df.columns:
        df = df[df["contract_symbol"].astype(str).str.len() > 0]
    if "expiration" in df.columns:
        df = df[pd.to_numeric(df["expiration"], errors="coerce").fillna(0) > 0]
    if "strike" in df.columns:
        df = df[pd.to_numeric(df["strike"], errors="coerce").fillna(0) > 0]

    if df.empty:
        return 0

    # Deduplicate within the payload to avoid Postgres "affect row a second time" errors
    df = df.drop_duplicates(subset=["expiration", "strike", "side"], keep="first")

    df_ohlc = db.fetch_ohlc_bars(underlying, timeframe="d1", limit=100)
    trend = determine_trend(df_ohlc)

    iv_stats = fetch_iv_stats(symbol_id)
    options_history = ensure_options_history(underlying, required_days=5)
    prev = fetch_previous_rankings(symbol_id, "entry")

    ranker = OptionsMomentumRanker()
    ranked = ranker.rank_options(
        df,
        iv_stats=iv_stats,
        options_history=options_history if not options_history.empty else None,
        underlying_trend=trend,
        previous_rankings=prev if not prev.empty else None,
        ranking_mode="entry",
    )

    batch: list[dict[str, Any]] = []
    skip_logged = 0
    for _, row in ranked.iterrows():
        expiration_raw = row.get("expiration", 0)
        exp_num = pd.to_numeric(expiration_raw, errors="coerce")
        if not pd.notna(exp_num) or float(exp_num) <= 0:
            if skip_logged < 3:
                logger.info(f"Skipping row with bad expiration: {expiration_raw}")
                skip_logged += 1
            skipped += 1
            continue

        side = row.get("side", "call")
        if side not in ("call", "put"):
            if skip_logged < 3:
                logger.info(f"Skipping row with bad side: {side}")
                skip_logged += 1
            skipped += 1
            continue

        contract_symbol = str(row.get("contract_symbol", "") or "")
        if not contract_symbol:
            if skip_logged < 3:
                logger.info("Skipping row with empty contract_symbol")
                skip_logged += 1
            skipped += 1
            continue

        expiry_date = datetime.fromtimestamp(int(exp_num)).date()
        composite_rank = _float_or_zero(row.get("composite_rank", 0.0))

        batch.append(
            {
                "underlying_symbol_id": symbol_id,
                "ranking_mode": "entry",
                "contract_symbol": contract_symbol,
                "expiry": expiry_date.isoformat(),
                "strike": _float_or_zero(row.get("strike", 0.0)),
                "side": side,
                "ml_score": round(composite_rank / 100.0, 4),
                "implied_vol": _float_or_none(row.get("iv")),
                "delta": _float_or_none(row.get("delta")),
                "gamma": _float_or_none(row.get("gamma")),
                "theta": _float_or_none(row.get("theta")),
                "vega": _float_or_none(row.get("vega")),
                "rho": _float_or_none(row.get("rho")),
                "bid": _float_or_none(row.get("bid")),
                "ask": _float_or_none(row.get("ask")),
                "mark": _float_or_none(row.get("mark")),
                "last_price": _float_or_none(row.get("last_price")),
                "volume": _int_or_zero(row.get("volume", 0)),
                "open_interest": _int_or_zero(row.get("open_interest", 0)),
                "run_at": run_at,
                "composite_rank": composite_rank,
                "momentum_score": _float_or_zero(row.get("momentum_score", 0.0)),
                "value_score": _float_or_zero(row.get("value_score", 0.0)),
                "greeks_score": _float_or_zero(row.get("greeks_score", 0.0)),
                "iv_rank": _float_or_none(row.get("iv_rank")),
                "spread_pct": _float_or_none(row.get("spread_pct")),
                "vol_oi_ratio": _float_or_none(row.get("vol_oi_ratio")),
                "liquidity_confidence": _float_or_none(row.get("liquidity_confidence", 1.0)),
                "relative_value_score": _float_or_none(row.get("relative_value_score")),
                "entry_difficulty_score": _float_or_none(row.get("entry_difficulty_score")),
                "ranking_stability_score": _float_or_none(row.get("ranking_stability_score")),
                "signal_discount": bool(row.get("signal_discount", False)),
                "signal_runner": bool(row.get("signal_runner", False)),
                "signal_greeks": bool(row.get("signal_greeks", False)),
                "signal_buy": bool(row.get("signal_buy", False)),
                "signals": str(row.get("signals", "")),
            }
        )

    # Insert in batches - no slow fallback, just retry once and move on
    total_batches = (len(batch) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num, i in enumerate(range(0, len(batch), BATCH_SIZE), 1):
        chunk = batch[i : i + BATCH_SIZE]
        for attempt in range(2):  # Max 2 attempts per batch
            try:
                db.client.table("options_ranks").upsert(
                    chunk,
                    on_conflict="underlying_symbol_id,ranking_mode,expiry,strike,side",
                ).execute()
                updated += len(chunk)
                break  # Success, move to next batch
            except Exception as e:
                if attempt == 0:
                    logger.debug(
                        "Ranks batch %s/%s failed, retrying: %s",
                        batch_num,
                        total_batches,
                        e,
                    )
                    time.sleep(1)  # Brief pause before retry
                else:
                    logger.warning(
                        "Ranks batch %s/%s failed after retry, skipping %s " "records: %s",
                        batch_num,
                        total_batches,
                        len(chunk),
                        e,
                    )
                    skipped += len(chunk)

    logger.info(
        "Updated %s option ranks for %s (%s skipped)",
        updated,
        underlying,
        skipped,
    )
    return updated


def process_symbol(underlying: str, snapshot_date: date) -> Dict[str, Any]:
    """
    Process a single symbol: fetch chain, store snapshot, update ranks.
    Returns summary stats.
    """
    logger.info(f"{'='*60}")
    logger.info(f"Processing {underlying}")
    logger.info(f"{'='*60}")

    try:
        # Fetch options chain (all expirations)
        chain_data = fetch_options_chain(underlying)
        calls = chain_data.get("calls", [])
        puts = chain_data.get("puts", [])

        if not calls and not puts:
            logger.warning(f"No options data for {underlying}")
            return {"symbol": underlying, "success": False, "error": "No data"}

        # Calculate ML scores first so we can include them in snapshots
        ml_scores = calculate_ml_scores(underlying, calls, puts)

        # Store snapshot with ml_scores
        snapshot_inserted, snapshot_skipped = persist_options_snapshot(
            underlying, calls, puts, snapshot_date, ml_scores=ml_scores
        )

        # Update ranks (uses same scoring logic)
        ranks_updated = update_options_ranks(underlying, calls, puts)

        return {
            "symbol": underlying,
            "success": True,
            "calls": len(calls),
            "puts": len(puts),
            "snapshots_inserted": snapshot_inserted,
            "ranks_updated": ranks_updated,
        }

    except Exception as e:
        logger.error(f"Failed to process {underlying}: {e}")
        return {"symbol": underlying, "success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description=("Nightly options chain backfill with snapshot storage and ranking")
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol", type=str, help="Single symbol to process (e.g., AAPL)")
    group.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Multiple symbols to process (e.g., AAPL TSLA NVDA)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Process all watchlist symbols from database",
    )

    args = parser.parse_args()

    # Determine which symbols to process
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:  # --all
        symbols = get_watchlist_symbols_from_db(limit=200)

    snapshot_date = date.today()
    overall_start_time = time.time()

    logger.info("=" * 60)
    logger.info("Options Nightly Backfill Script")
    logger.info(f"Snapshot Date: {snapshot_date}")
    logger.info(f"Processing {len(symbols)} symbol(s)")
    logger.info("=" * 60)

    results = []
    success_count = 0
    failure_count = 0

    for i, symbol in enumerate(symbols):
        result = process_symbol(symbol, snapshot_date)
        results.append(result)

        if result["success"]:
            success_count += 1
        else:
            failure_count += 1

        # Rate limiting between symbols
        if i < len(symbols) - 1:
            logger.info(f"Rate limit delay ({RATE_LIMIT_DELAY}s)...")
            time.sleep(RATE_LIMIT_DELAY)

    overall_elapsed = time.time() - overall_start_time

    # Summary
    total_calls = sum(r.get("calls", 0) for r in results if r.get("success"))
    total_puts = sum(r.get("puts", 0) for r in results if r.get("success"))
    total_snapshots = sum(r.get("snapshots_inserted", 0) for r in results if r.get("success"))
    total_ranks = sum(r.get("ranks_updated", 0) for r in results if r.get("success"))

    logger.info("")
    logger.info("=" * 60)
    logger.info("Options Nightly Backfill Complete")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {failure_count}")
    logger.info(f"Total Calls: {total_calls}")
    logger.info(f"Total Puts: {total_puts}")
    logger.info(f"Snapshots Stored: {total_snapshots}")
    logger.info(f"Ranks Updated: {total_ranks}")
    logger.info(f"Total time: {overall_elapsed:.1f}s")
    logger.info("=" * 60)

    # Exit with non-zero code if any failures
    sys.exit(0 if failure_count == 0 else 1)


if __name__ == "__main__":
    main()
