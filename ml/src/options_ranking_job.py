"""Options ranking job that scores option contracts using Momentum Framework.

Uses OptionsMomentumRanker exclusively for all scoring. The Momentum Framework
produces composite_rank (0-100) based on:
- Momentum Score (40%): Price momentum, volume/OI ratio, OI growth
- Value Score (35%): IV Rank, bid-ask spread tightness
- Greeks Score (25%): Delta quality, gamma, vega, theta penalty
"""

import argparse
import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.models.options_momentum_ranker import (  # noqa: E402
    CalibratedMomentumRanker,
    IVStatistics,
    OptionsMomentumRanker,
)
from src.options_historical_backfill import ensure_options_history  # noqa: E402

# Use constant from OptionsMomentumRanker for consistency
TRADING_DAYS_PER_YEAR = OptionsMomentumRanker.TRADING_DAYS_PER_YEAR

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
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"Fetched {len(data.get('calls', []))} calls and {len(data.get('puts', []))} puts"
        )
        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch options chain for {symbol}: {e}")
        raise


def parse_options_chain(api_response: dict) -> pd.DataFrame:
    """Parse options chain API response into DataFrame with camelCase columns for ranker."""
    contracts = []

    for call in api_response.get("calls", []):
        contracts.append(
            {
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
            }
        )

    for put in api_response.get("puts", []):
        contracts.append(
            {
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
            }
        )

    return pd.DataFrame(contracts)


def calculate_days_to_expiry(expiration_ts: int) -> int:
    """Calculate days to expiration from Unix timestamp."""
    expiry_date = datetime.fromtimestamp(expiration_ts)
    today = datetime.now()
    return (expiry_date - today).days


def select_balanced_expiry_contracts(
    ranked_df: pd.DataFrame, total_contracts: int = 100
) -> pd.DataFrame:
    """
    Select top contracts with balanced distribution across expiry ranges.

    Ensures we don't over-weight near-expiry ITM options by distributing
    selections across different time horizons:
    - Near-term (7-30 days): 30%
    - Mid-term (30-60 days): 40%
    - Long-term (60+ days): 30%

    Within each bucket, takes top contracts by composite_rank.

    Args:
        ranked_df: DataFrame of ranked options with composite_rank and expiration columns
        total_contracts: Total number of contracts to select (default: 100)

    Returns:
        DataFrame with balanced selection of top contracts
    """
    if ranked_df.empty:
        return ranked_df

    # Add DTE column
    ranked_df = ranked_df.copy()
    ranked_df["dte"] = ranked_df["expiration"].apply(calculate_days_to_expiry)

    # Define expiry buckets
    near_term = ranked_df[ranked_df["dte"].between(7, 30)]
    mid_term = ranked_df[ranked_df["dte"].between(30, 60)]
    long_term = ranked_df[ranked_df["dte"] >= 60]
    very_short = ranked_df[ranked_df["dte"] < 7]  # Less than 1 week

    # Allocate contract counts
    near_count = int(total_contracts * 0.30)
    mid_count = int(total_contracts * 0.40)
    long_count = int(total_contracts * 0.25)
    very_short_count = int(total_contracts * 0.05)  # Only 5% for very short

    # Select top from each bucket by composite_rank
    selected_contracts = []

    if not very_short.empty:
        selected_contracts.append(very_short.nlargest(very_short_count, "composite_rank"))

    if not near_term.empty:
        selected_contracts.append(near_term.nlargest(near_count, "composite_rank"))

    if not mid_term.empty:
        selected_contracts.append(mid_term.nlargest(mid_count, "composite_rank"))

    if not long_term.empty:
        selected_contracts.append(long_term.nlargest(long_count, "composite_rank"))

    # If we didn't get enough contracts from buckets, backfill with top overall
    if selected_contracts:
        result = pd.concat(selected_contracts, ignore_index=True)
    else:
        result = pd.DataFrame()

    if len(result) < total_contracts:
        # FIX: Use contract_symbol for exclusion instead of index to avoid
        # inconsistencies if indexes were reset earlier
        remaining_count = total_contracts - len(result)
        selected_symbols = set(result["contract_symbol"].tolist()) if not result.empty else set()
        excluded = ranked_df[~ranked_df["contract_symbol"].isin(selected_symbols)]
        if not excluded.empty:
            backfill = excluded.nlargest(remaining_count, "composite_rank")
            result = pd.concat([result, backfill], ignore_index=True)

    # Sort by composite_rank descending
    result = result.sort_values("composite_rank", ascending=False)

    # Drop the temporary DTE column before returning
    result = result.drop(columns=["dte"])

    logger.info(
        f"Selected {len(result)} contracts: "
        f"{len(very_short.nlargest(very_short_count, 'composite_rank'))} very short-term, "
        f"{len(near_term.nlargest(near_count, 'composite_rank'))} near-term, "
        f"{len(mid_term.nlargest(mid_count, 'composite_rank'))} mid-term, "
        f"{len(long_term.nlargest(long_count, 'composite_rank'))} long-term"
    )

    return result


def build_contract_symbol(
    underlying: str,
    expiry: str,
    strike: float,
    side: str,
) -> str:
    """
    Build OCC-format contract symbol from components.

    Format: SYMBOL + YYMMDD + C/P + Strike*1000 (8 digits, zero-padded)
    Example: AAPL240119C00150000 = AAPL, 2024-01-19, Call, $150

    Args:
        underlying: Stock ticker symbol
        expiry: Expiration date in 'YYYY-MM-DD' format
        strike: Strike price
        side: Option type ('call' or 'put')

    Returns:
        OCC-format contract symbol
    """
    exp_date = datetime.strptime(expiry, "%Y-%m-%d")
    exp_str = exp_date.strftime("%y%m%d")
    opt_char = "C" if side.lower() == "call" else "P"
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    return f"{underlying.upper()}{exp_str}{opt_char}{strike_str}"


def fetch_specific_option_quotes(
    symbol: str,
    contracts: list[str],
) -> dict[str, dict]:
    """
    Fetch live quotes for specific option contracts via options-quotes Edge Function.

    Args:
        symbol: Underlying ticker symbol
        contracts: List of OCC-format contract symbols to fetch

    Returns:
        Dict mapping contract_symbol -> quote data (bid, ask, mark, Greeks)
    """
    if not contracts:
        return {}

    url = f"{settings.supabase_url}/functions/v1/options-quotes"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "symbol": symbol,
        "contracts": contracts,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        result = {}
        for quote in data.get("quotes", []):
            symbol_key = quote.get("contract_symbol")
            if symbol_key:
                result[symbol_key] = {
                    "bid": quote.get("bid") or 0,
                    "ask": quote.get("ask") or 0,
                    "mark": quote.get("mark") or (
                        ((quote.get("bid") or 0) + (quote.get("ask") or 0)) / 2
                    ),
                    "last": quote.get("last") or 0,
                    "volume": quote.get("volume") or 0,
                    "open_interest": quote.get("open_interest") or 0,
                    "implied_vol": quote.get("implied_vol") or 0,
                    "delta": quote.get("delta") or 0,
                    "gamma": quote.get("gamma") or 0,
                    "theta": quote.get("theta") or 0,
                    "vega": quote.get("vega") or 0,
                    "rho": quote.get("rho") or 0,
                }

        logger.info(
            f"Fetched quotes for {len(result)}/{len(contracts)} strategy contracts"
        )
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch strategy option quotes: {e}")
        return {}


def _sanitize_number(value: float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    return num


def save_rankings_to_db(symbol_id: str, ranked_df: pd.DataFrame) -> int:
    """Save ranked options to database with momentum framework scores."""
    saved_count = 0
    run_at = datetime.utcnow().isoformat()

    for _, row in ranked_df.iterrows():
        try:
            # Convert expiration timestamp to date string
            expiry_date = datetime.fromtimestamp(row["expiration"]).strftime("%Y-%m-%d")

            # Get composite_rank (primary score from Momentum Framework)
            composite_rank = _sanitize_number(row.get("composite_rank", 0))

            # Build record with all columns
            # ml_score is derived from composite_rank for backwards compatibility
            record = {
                "underlying_symbol_id": symbol_id,
                "contract_symbol": row["contract_symbol"],
                "expiry": expiry_date,
                "strike": _sanitize_number(row["strike"]),
                "side": row["side"],
                "ml_score": composite_rank / 100.0,  # Normalize to 0-1 for legacy field
                "implied_vol": _sanitize_number(
                    row.get("impliedVolatility", row.get("iv", 0))
                ),
                "delta": _sanitize_number(row.get("delta", 0)),
                "gamma": _sanitize_number(row.get("gamma", 0)),
                "theta": _sanitize_number(row.get("theta", 0)),
                "vega": _sanitize_number(row.get("vega", 0)),
                "rho": _sanitize_number(row.get("rho", 0)),
                "bid": _sanitize_number(row.get("bid", 0)),
                "ask": _sanitize_number(row.get("ask", 0)),
                "mark": _sanitize_number(row.get("mark", 0)),
                "last_price": _sanitize_number(row.get("last_price", 0)),
                "volume": int(_sanitize_number(row.get("volume", 0))),
                "open_interest": int(
                    _sanitize_number(row.get("openInterest", row.get("open_interest", 0)))
                ),
                "run_at": run_at,
                # Momentum Framework scores
                "composite_rank": composite_rank,
                "momentum_score": _sanitize_number(row.get("momentum_score", 0)),
                "value_score": _sanitize_number(row.get("value_score", 0)),
                "greeks_score": _sanitize_number(row.get("greeks_score", 0)),
                "iv_rank": _sanitize_number(row.get("iv_rank", 0)),
                "spread_pct": _sanitize_number(row.get("spread_pct", 0)),
                "vol_oi_ratio": _sanitize_number(row.get("vol_oi_ratio", 0)),
                "liquidity_confidence": _sanitize_number(row.get("liquidity_confidence", 1.0)),
                "ranking_mode": str(row.get("ranking_mode", "entry")),
                "relative_value_score": _sanitize_number(row.get("relative_value_score", 0)),
                "entry_difficulty_score": _sanitize_number(
                    row.get("entry_difficulty_score", 0)
                ),
                "ranking_stability_score": _sanitize_number(
                    row.get("ranking_stability_score", 0)
                ),
                "iv_curve_ok": bool(row.get("iv_curve_ok", True)),
                "iv_data_quality_score": _sanitize_number(
                    row.get("iv_data_quality_score", 1.0)
                ),
                # Signals
                "signal_discount": bool(row.get("signal_discount", False)),
                "signal_runner": bool(row.get("signal_runner", False)),
                "signal_greeks": bool(row.get("signal_greeks", False)),
                "signal_buy": bool(row.get("signal_buy", False)),
                # FIX: Store signals as JSON array for consistent parsing
                "signals": json.dumps(
                    row.get("signals", "").split(",")
                    if row.get("signals")
                    else []
                ),
            }

            db.upsert_option_rank_extended(**record)
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving rank for {row.get('contract_symbol')}: {e}")

    return saved_count


def fetch_previous_rankings(symbol_id: str, ranking_mode: str) -> pd.DataFrame:
    """Fetch previous rankings for a symbol/mode to enable smoothing/stability."""
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
                "contract_symbol,strike,side,composite_rank,momentum_score,value_score,"
                "greeks_score,ranking_mode"
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


def fetch_iv_stats(symbol_id: str) -> IVStatistics | None:
    """Fetch 52-week IV statistics for a symbol."""
    try:
        result = db.client.rpc("calculate_iv_rank", {"p_symbol_id": symbol_id}).execute()
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return IVStatistics(
                iv_current=row.get("iv_current", 0.3),
                iv_high=row.get("iv_52_high", 0.5),
                iv_low=row.get("iv_52_low", 0.2),
                iv_median=row.get("iv_52_high", 0.35) * 0.7,  # Estimate
            )
    except Exception as e:
        logger.warning(f"Could not fetch IV stats: {e}")
    return None


def determine_trend(df_ohlc: pd.DataFrame) -> str:
    """Determine underlying trend from OHLC data."""
    if len(df_ohlc) < 20:
        return "neutral"

    # Simple trend detection using moving averages
    close = df_ohlc["close"]
    sma_10 = close.tail(10).mean()
    sma_20 = close.tail(20).mean()
    current = close.iloc[-1]

    if current > sma_10 > sma_20:
        return "bullish"
    elif current < sma_10 < sma_20:
        return "bearish"
    return "neutral"


def process_symbol_options(
    symbol: str,
    ranking_mode: str = "entry",
    use_calibration: bool = True,
    use_regime_conditioning: bool = True,
) -> None:
    """
    Process options for a single symbol: fetch data, rank contracts, save rankings.

    Uses CalibratedMomentumRanker with:
    - Isotonic calibration to forward return percentiles
    - Regime-conditioned weights (trend/vol regime)
    - Integration with ranking monitor for alerts

    Args:
        symbol: Stock ticker symbol
        ranking_mode: 'entry' or 'exit'
        use_calibration: Apply isotonic calibration
        use_regime_conditioning: Adjust weights by market regime
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
        underlying_trend = determine_trend(df_ohlc)

        # Calculate historical volatility (20-day)
        returns = df_ohlc.tail(20)["close"].pct_change().dropna()
        historical_vol = returns.std() * (252**0.5)  # Annualized

        logger.info(
            f"{symbol}: price=${underlying_price:.2f}, "
            f"HV={historical_vol:.2%}, trend={underlying_trend}"
        )

        # Fetch 7-day underlying metrics from database (if available)
        underlying_metrics = db.get_underlying_metrics(symbol_id, timeframe="d1")
        if underlying_metrics:
            logger.info(
                f"{symbol} 7d metrics: ret={underlying_metrics.get('ret_7d', 0):.2f}%, "
                f"vol={underlying_metrics.get('vol_7d', 0):.1f}%, "
                f"drawdown={underlying_metrics.get('drawdown_7d', 0):.1f}%"
            )
        else:
            # Compute 7-day metrics from OHLC data if not in database
            if len(df_ohlc) >= 7:
                recent_ohlc = df_ohlc.tail(7)
                close_prices = recent_ohlc["close"].astype(float)

                # Calculate basic metrics
                ret_7d = (
                    (close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0] * 100
                    if close_prices.iloc[0] > 0
                    else 0.0
                )
                vol_7d = close_prices.pct_change().dropna().std() * (TRADING_DAYS_PER_YEAR**0.5) * 100

                underlying_metrics = {
                    "ret_7d": ret_7d,
                    "vol_7d": vol_7d,
                    "drawdown_7d": 0.0,  # Simplified
                    "gap_count": 0,
                }
                logger.info(f"{symbol} computed 7d metrics from OHLC: ret={ret_7d:.2f}%")

        # Fetch options chain from API
        api_response = fetch_options_from_api(symbol)
        options_df = parse_options_chain(api_response)

        if options_df.empty:
            logger.warning(f"No options contracts found for {symbol}")
            return

        logger.info(f"Parsed {len(options_df)} contracts for {symbol}")

        # Fetch IV statistics for IV Rank calculation
        iv_stats = fetch_iv_stats(symbol_id)

        # Ensure historical options data exists for momentum calculations
        logger.info(f"Ensuring historical options data for {symbol}...")
        options_history = ensure_options_history(symbol, required_days=5)

        if options_history.empty:
            logger.warning(
                f"No historical data available for {symbol}, " "momentum scores will be estimated"
            )

        # Use CalibratedMomentumRanker with regime conditioning
        ranker = CalibratedMomentumRanker(
            enable_calibration=use_calibration,
            enable_regime_conditioning=use_regime_conditioning,
        )

        # Try to load existing calibrator if available
        calibrator_path = Path(__file__).parent / f"calibrators/{symbol}_cal.json"
        if calibrator_path.exists() and use_calibration:
            try:
                ranker.load_calibrator(str(calibrator_path))
                logger.info(f"Loaded calibrator from {calibrator_path}")
            except Exception as e:
                logger.warning(f"Could not load calibrator: {e}")

        previous_rankings = fetch_previous_rankings(symbol_id, ranking_mode)

        # Use calibrated ranking with regime conditioning and underlying metrics
        ranked_df = ranker.rank_options_calibrated(
            options_df,
            iv_stats=iv_stats,
            options_history=options_history if not options_history.empty else None,
            underlying_df=df_ohlc if use_regime_conditioning else None,
            underlying_trend=underlying_trend,
            previous_rankings=(previous_rankings if not previous_rankings.empty else None),
            ranking_mode=ranking_mode,
            underlying_metrics=underlying_metrics,
        )

        # Log regime info if available
        if "trend_regime" in ranked_df.columns:
            regime_info = ranked_df.iloc[0]
            logger.info(
                f"Regime: {regime_info.get('trend_regime', 'N/A')}/"
                f"{regime_info.get('vol_regime', 'N/A')}, "
                f"ADX={regime_info.get('regime_adx', 0):.1f}"
            )

        # Log calibration info if available
        if "calibrated_positive_prob" in ranked_df.columns:
            top_prob = ranked_df["calibrated_positive_prob"].max()
            logger.info(f"Top calibrated P(+): {top_prob:.2%}")

        logger.info(
            f"Ranked {len(ranked_df)} contracts, "
            f"composite range {ranked_df['composite_rank'].min():.1f}-"
            f"{ranked_df['composite_rank'].max():.1f}"
        )

        # Log signal counts
        if "signal_buy" in ranked_df.columns:
            buy_count = ranked_df["signal_buy"].sum()
            discount_count = ranked_df["signal_discount"].sum()
            runner_count = ranked_df["signal_runner"].sum()
            greeks_count = ranked_df["signal_greeks"].sum()
            logger.info(
                f"Signals: BUY={buy_count}, DISCOUNT={discount_count}, "
                f"RUNNER={runner_count}, GREEKS={greeks_count}"
            )

        # Save top contracts with balanced expiry distribution
        top_ranked = select_balanced_expiry_contracts(ranked_df)
        saved_count = save_rankings_to_db(symbol_id, top_ranked)

        logger.info(f"Saved {saved_count} ranked contracts for {symbol}")

        # Include options from active multi-leg strategies
        active_strategy_options = db.get_active_strategy_options(symbol_id)

        if active_strategy_options:
            logger.info(
                f"Found {len(active_strategy_options)} active strategy options for {symbol}"
            )

            # Build set of (expiry, strike, side) from top_ranked for deduplication
            top_ranked_keys: set[tuple[str, float, str]] = set()
            for _, row in top_ranked.iterrows():
                exp_date = datetime.fromtimestamp(row["expiration"]).strftime("%Y-%m-%d")
                top_ranked_keys.add((exp_date, row["strike"], row["side"]))

            # Identify strategy options NOT in top-ranked
            missing_options = []
            for opt in active_strategy_options:
                key = (opt["expiry"], opt["strike"], opt["side"])
                if key not in top_ranked_keys:
                    missing_options.append(opt)

            if missing_options:
                logger.info(
                    f"Adding {len(missing_options)} strategy options not in top-ranked"
                )

                # Build contract symbols for missing options
                missing_symbols = []
                for opt in missing_options:
                    contract_sym = build_contract_symbol(
                        symbol, opt["expiry"], opt["strike"], opt["side"]
                    )
                    missing_symbols.append(contract_sym)
                    opt["contract_symbol"] = contract_sym

                # Fetch live quotes for missing options
                quotes = fetch_specific_option_quotes(symbol, missing_symbols)

                # Save strategy options to options_ranks
                run_at = datetime.utcnow().isoformat()
                strategy_saved = 0

                for opt in missing_options:
                    contract_sym = opt["contract_symbol"]
                    quote = quotes.get(contract_sym, {})

                    record = {
                        "underlying_symbol_id": symbol_id,
                        "contract_symbol": contract_sym,
                        "expiry": opt["expiry"],
                        "strike": _sanitize_number(opt["strike"]),
                        "side": opt["side"],
                        "ml_score": 0.0,
                        "implied_vol": _sanitize_number(quote.get("implied_vol", 0)),
                        "delta": _sanitize_number(quote.get("delta", 0)),
                        "gamma": _sanitize_number(quote.get("gamma", 0)),
                        "theta": _sanitize_number(quote.get("theta", 0)),
                        "vega": _sanitize_number(quote.get("vega", 0)),
                        "rho": _sanitize_number(quote.get("rho", 0)),
                        "bid": _sanitize_number(quote.get("bid", 0)),
                        "ask": _sanitize_number(quote.get("ask", 0)),
                        "mark": _sanitize_number(quote.get("mark", 0)),
                        "last_price": _sanitize_number(quote.get("last", 0)),
                        "volume": int(_sanitize_number(quote.get("volume", 0))),
                        "open_interest": int(
                            _sanitize_number(quote.get("open_interest", 0))
                        ),
                        "run_at": run_at,
                        "composite_rank": 0.0,
                        "momentum_score": 0.0,
                        "value_score": 0.0,
                        "greeks_score": 0.0,
                        "iv_rank": 0.0,
                        "spread_pct": 0.0,
                        "vol_oi_ratio": 0.0,
                        "liquidity_confidence": 0.0,
                        "ranking_mode": "strategy",
                        "signal_discount": False,
                        "signal_runner": False,
                        "signal_greeks": False,
                        "signal_buy": False,
                        "signals": "[]",
                    }

                    try:
                        db.upsert_option_rank_extended(**record)
                        strategy_saved += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to save strategy option {contract_sym}: {e}"
                        )

                logger.info(
                    f"Saved {strategy_saved} strategy options for {symbol}"
                )

    except Exception as e:
        logger.error(f"Error processing options for {symbol}: {e}", exc_info=True)


def main() -> None:
    """Main options ranking job entry point."""
    parser = argparse.ArgumentParser(description="Rank options contracts using Momentum Framework")
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to process (e.g., AAPL). If not provided, uses settings.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="entry",
        choices=["entry", "exit"],
        help="Ranking mode: entry (default) or exit.",
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
            process_symbol_options(symbol, ranking_mode=args.mode)
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
