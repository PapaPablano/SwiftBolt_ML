"""Options chain and quotes router — live data from Alpaca and Tradier for fresher Options Ranker.

Uses Alpaca first (when credentials are set), then Tradier as fallback. Same
response shape as Supabase Edge options-chain and options-quotes so the macOS
client can use FastAPI (Docker) for live options data when available.

Optional short-TTL Redis cache for options chain and quotes to reduce Alpaca/Tradier
calls when the same symbol/contracts are requested repeatedly (e.g. polling).
"""

import hashlib
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Add ml root for imports
ml_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ml_dir))

logger = logging.getLogger(__name__)
router = APIRouter()

ALPACA_OPTIONS_BASE = "https://data.alpaca.markets/v1beta1/options"
_tradier_client = None
_redis_client = None


def _options_cache_ttl_seconds() -> int:
    """Options cache TTL from env (default 60s for quotes/chain)."""
    try:
        return max(10, int(os.getenv("OPTIONS_CACHE_TTL_SECONDS", "60")))
    except Exception:
        return 60


def _options_cache_enabled() -> bool:
    return os.getenv("ENABLE_OPTIONS_CACHE", "true").strip().lower() in ("1", "true", "yes", "y", "on")


def _get_redis():
    """Lazy Redis client for options cache; None if disabled or unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not _options_cache_enabled():
        return None
    try:
        import redis
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.debug("Options cache Redis unavailable: %s", e)
        return None


def _options_chain_cache_key(underlying: str, expiration: int | None) -> str:
    return f"options_chain:v1:{underlying}:{expiration if expiration else 'all'}"


def _options_quotes_cache_key(symbol: str, contracts: list[str]) -> str:
    h = hashlib.sha256(",".join(sorted(c.upper() for c in contracts)).encode()).hexdigest()[:24]
    return f"options_quotes:v1:{symbol}:{h}"


def _get_options_chain_cached(underlying: str, expiration: int | None):
    r = _get_redis()
    if not r:
        return None
    try:
        key = _options_chain_cache_key(underlying, expiration)
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug("Options chain cache get error: %s", e)
    return None


def _set_options_chain_cached(underlying: str, expiration: int | None, data: dict) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        key = _options_chain_cache_key(underlying, expiration)
        r.setex(key, _options_cache_ttl_seconds(), json.dumps(data, default=str))
    except Exception as e:
        logger.debug("Options chain cache set error: %s", e)


def _get_options_quotes_cached(symbol: str, contracts: list[str]):
    r = _get_redis()
    if not r:
        return None
    try:
        key = _options_quotes_cache_key(symbol, contracts)
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug("Options quotes cache get error: %s", e)
    return None


def _set_options_quotes_cached(symbol: str, contracts: list[str], data: dict) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        key = _options_quotes_cache_key(symbol, contracts)
        r.setex(key, _options_cache_ttl_seconds(), json.dumps(data, default=str))
    except Exception as e:
        logger.debug("Options quotes cache set error: %s", e)


def _json_safe_float(v):
    """Return float or None; None for NaN/Inf so JSON serialization succeeds."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _alpaca_configured() -> bool:
    """True if Alpaca API keys are set."""
    try:
        from config.settings import settings
        return bool(getattr(settings, "alpaca_api_key", None) and getattr(settings, "alpaca_api_secret", None))
    except Exception:
        return False


def _parse_occ_symbol(symbol: str) -> dict | None:
    """Parse OCC option symbol to strike, expiration (Unix), type. e.g. AAPL250117C00250000."""
    symbol = (symbol or "").strip()
    if len(symbol) < 21:
        return None
    try:
        root = symbol[:6].rstrip()
        yy, mm, dd = int(symbol[6:8]), int(symbol[8:10]), int(symbol[10:12])
        year = 2000 + yy if yy < 80 else 1900 + yy
        exp_ts = int(datetime(year, mm, dd, tzinfo=timezone.utc).timestamp())
        type_char = symbol[12].upper()
        opt_type = "call" if type_char == "C" else "put"
        strike_cents = int(symbol[13:21])
        strike = strike_cents / 1000.0
        return {"underlying": root, "expiration": exp_ts, "type": opt_type, "strike": strike}
    except (ValueError, IndexError):
        return None


def _fetch_alpaca_options_chain(underlying: str, expiration_ts: int | None) -> dict | None:
    """Fetch options chain from Alpaca; return Edge-shaped dict or None on failure."""
    try:
        from config.settings import settings
        key = getattr(settings, "alpaca_api_key", None)
        secret = getattr(settings, "alpaca_api_secret", None)
        if not key or not secret:
            return None
    except Exception:
        return None
    url = f"{ALPACA_OPTIONS_BASE}/snapshots/{underlying}?feed=indicative"
    if expiration_ts:
        exp_date = datetime.utcfromtimestamp(expiration_ts).strftime("%Y-%m-%d")
        url += f"&expiration_date={exp_date}"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                url,
                headers={
                    "APCA-API-KEY-ID": key,
                    "APCA-API-SECRET-KEY": secret,
                    "Accept": "application/json",
                },
            )
            if r.status_code != 200:
                logger.warning("Alpaca options snapshot status %s: %s", r.status_code, r.text[:200])
                return None
            data = r.json()
    except Exception as e:
        logger.warning("Alpaca options fetch failed: %s", e)
        return None
    snapshots = data.get("snapshots") or {}
    calls = []
    puts = []
    expirations_set = set()
    for opt_sym, snap in snapshots.items():
        parsed = _parse_occ_symbol(opt_sym)
        if not parsed or parsed.get("underlying", "").rstrip() != underlying:
            continue
        quote = (snap.get("latestQuote") or {})
        trade = (snap.get("latestTrade") or {})
        greeks = (snap.get("greeks") or {})
        bid = quote.get("bp")
        ask = quote.get("ap")
        last = trade.get("p")
        bid = _json_safe_float(bid)
        ask = _json_safe_float(ask)
        last = _json_safe_float(last)
        mark = (bid + ask) / 2 if (bid is not None and ask is not None) else last
        mark = _json_safe_float(mark) if mark is not None else None
        vol = (snap.get("dailyBar") or {}).get("v") or 0
        oi = snap.get("openInterest") or 0
        try:
            vol = int(vol)
            oi = int(oi)
        except (TypeError, ValueError):
            vol = 0
            oi = 0
        last_ts = trade.get("t")
        last_trade_time = int(datetime.fromisoformat(last_ts.replace("Z", "+00:00")).timestamp()) if last_ts else None
        expirations_set.add(parsed["expiration"])
        c = {
            "symbol": opt_sym,
            "underlying": underlying,
            "strike": _json_safe_float(parsed["strike"]) or parsed["strike"],
            "expiration": parsed["expiration"],
            "type": parsed["type"],
            "bid": bid,
            "ask": ask,
            "last": last,
            "mark": mark,
            "volume": vol,
            "openInterest": oi,
            "delta": _json_safe_float(greeks.get("delta")),
            "gamma": _json_safe_float(greeks.get("gamma")),
            "theta": _json_safe_float(greeks.get("theta")),
            "vega": _json_safe_float(greeks.get("vega")),
            "rho": _json_safe_float(greeks.get("rho")),
            "impliedVolatility": _json_safe_float(snap.get("impliedVolatility")),
            "lastTradeTime": last_trade_time,
            "changePercent": None,
            "change": None,
        }
        if parsed["type"] == "call":
            calls.append(c)
        else:
            puts.append(c)
    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])
    return {
        "underlying": underlying,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "expirations": sorted(expirations_set),
        "calls": calls,
        "puts": puts,
    }


def _fetch_alpaca_options_quotes(symbol: str, contracts: list[str]) -> dict | None:
    """Fetch quotes for given option symbols from Alpaca; return Edge-shaped quotes response or None."""
    try:
        from config.settings import settings
        key = getattr(settings, "alpaca_api_key", None)
        secret = getattr(settings, "alpaca_api_secret", None)
        if not key or not secret or not contracts:
            return None
    except Exception:
        return None
    symbols_param = ",".join(contracts[:120])
    url = f"{ALPACA_OPTIONS_BASE}/quotes/latest?symbols={symbols_param}&feed=indicative"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                url,
                headers={
                    "APCA-API-KEY-ID": key,
                    "APCA-API-SECRET-KEY": secret,
                    "Accept": "application/json",
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None
    quotes_dict = data.get("quotes") or {}
    if not isinstance(quotes_dict, dict):
        quotes_dict = {}
    contract_set = set(c.upper() for c in contracts)
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    quotes = []
    for sym, q in quotes_dict.items():
        sym = (sym or "").upper()
        if sym not in contract_set:
            continue
        bp = q.get("bp")
        ap = q.get("ap")
        bid = _json_safe_float(bp)
        ask = _json_safe_float(ap)
        mark = (bid + ask) / 2 if (bid is not None and ask is not None) else None
        mark = _json_safe_float(mark) if mark is not None else None
        quotes.append({
            "contract_symbol": sym,
            "bid": bid,
            "ask": ask,
            "mark": mark,
            "last": None,
            "volume": None,
            "open_interest": None,
            "implied_vol": None,
            "updated_at": now_iso,
        })
    return {
        "symbol": symbol,
        "timestamp": now_iso,
        "chain_timestamp": now_iso,
        "total_requested": len(contracts),
        "total_returned": len(quotes),
        "quotes": quotes,
    }


def _get_tradier():
    """Lazy-init Tradier client; raises if not configured."""
    global _tradier_client
    if _tradier_client is not None:
        return _tradier_client
    try:
        from config.settings import settings
        from src.data.tradier_client import TradierClient
        if not (getattr(settings, "tradier_api_key", None)):
            raise ValueError("TRADIER_API_KEY not set")
        _tradier_client = TradierClient()
        return _tradier_client
    except Exception as e:
        logger.warning("Tradier client unavailable: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Options data requires at least one of ALPACA (API key/secret) or TRADIER_API_KEY.",
        ) from e


def _parse_expiration_to_unix(exp_date: str) -> int:
    """Parse YYYY-MM-DD to Unix timestamp (seconds, UTC)."""
    try:
        dt = datetime.strptime(exp_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def _row_to_contract(row, underlying: str) -> dict:
    """Convert a Tradier chain row to Edge-style contract (calls/puts)."""
    symbol = str(row.get("symbol", ""))
    exp_date = str(row.get("expiration_date", ""))
    strike = _json_safe_float(row.get("strike", 0)) or 0.0
    opt_type = str(row.get("option_type", "call")).lower()
    bid = _json_safe_float(row.get("bid"))
    ask = _json_safe_float(row.get("ask"))
    last = _json_safe_float(row.get("last"))
    mark = None
    if bid is not None and ask is not None:
        mark = _json_safe_float((bid + ask) / 2)
    if mark is None and last is not None:
        mark = last
    try:
        volume = int(row.get("volume") or 0)
    except (TypeError, ValueError):
        volume = 0
    try:
        oi = int(row.get("open_interest") or 0)
    except (TypeError, ValueError):
        oi = 0
    delta = _json_safe_float(row.get("greek_delta") or row.get("delta"))
    gamma = _json_safe_float(row.get("greek_gamma") or row.get("gamma"))
    theta = _json_safe_float(row.get("greek_theta") or row.get("theta"))
    vega = _json_safe_float(row.get("greek_vega") or row.get("vega"))
    rho = _json_safe_float(row.get("greek_rho") or row.get("rho"))
    iv = _json_safe_float(row.get("greek_mid_iv") or row.get("iv") or row.get("implied_volatility"))
    return {
        "symbol": symbol,
        "underlying": underlying,
        "strike": strike,
        "expiration": _parse_expiration_to_unix(exp_date),
        "type": "call" if opt_type == "call" else "put",
        "bid": bid,
        "ask": ask,
        "last": last,
        "mark": mark,
        "volume": volume,
        "openInterest": oi,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
        "impliedVolatility": iv,
        "lastTradeTime": None,
        "changePercent": None,
        "change": None,
    }


@router.get("/options-chain")
async def get_options_chain(
    underlying: str = Query(..., description="Underlying symbol (e.g. AAPL)"),
    expiration: int | None = Query(None, description="Optional expiration Unix timestamp (filter to that date)"),
):
    """
    Fetch live options chain from Alpaca (primary) or Tradier (fallback). Same
    response shape as Supabase options-chain Edge Function. Optionally served
    from short-TTL Redis cache when ENABLE_OPTIONS_CACHE is true.
    """
    underlying = (underlying or "").strip().upper()
    if not underlying:
        raise HTTPException(status_code=400, detail="underlying is required")

    # Optional: return cached chain (short TTL)
    cached = _get_options_chain_cached(underlying, expiration)
    if cached is not None:
        return cached

    # Try Alpaca first when credentials are set
    if _alpaca_configured():
        result = _fetch_alpaca_options_chain(underlying, expiration)
        if result and (result["calls"] or result["puts"]):
            _set_options_chain_cached(underlying, expiration, result)
            return result

    # Fall back to Tradier
    try:
        tradier = _get_tradier()
    except HTTPException:
        raise
    try:
        if expiration:
            from datetime import datetime as dt
            exp_date = dt.utcfromtimestamp(expiration).strftime("%Y-%m-%d")
            chain_df = tradier.get_options_chain(underlying, exp_date, greeks=True)
        else:
            chain_df = tradier.get_all_chains(underlying, max_expirations=6, greeks=True)
    except Exception as e:
        logger.exception("Tradier options chain fetch failed")
        raise HTTPException(status_code=502, detail=f"Failed to fetch options chain: {e}") from e
    if chain_df is None or chain_df.empty:
        return {
            "underlying": underlying,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "expirations": [],
            "calls": [],
            "puts": [],
        }
    expirations_set = set()
    calls = []
    puts = []
    for _, row in chain_df.iterrows():
        exp_date = str(row.get("expiration_date", ""))
        if exp_date:
            expirations_set.add(_parse_expiration_to_unix(exp_date))
        contract = _row_to_contract(row, underlying)
        if contract["type"] == "call":
            calls.append(contract)
        else:
            puts.append(contract)
    expirations = sorted(expirations_set)
    result = {
        "underlying": underlying,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "expirations": expirations,
        "calls": calls,
        "puts": puts,
    }
    _set_options_chain_cached(underlying, expiration, result)
    return result


class OptionsQuotesRequest(BaseModel):
    """Request body for options-quotes (same as Edge)."""
    symbol: str = Field(..., description="Underlying symbol")
    contracts: list[str] = Field(..., description="Option contract symbols (OCC)")


@router.post("/options-quotes")
async def post_options_quotes(body: OptionsQuotesRequest):
    """
    Return live quotes for the given option contracts from Alpaca (primary) or
    Tradier (fallback). Same response shape as Supabase options-quotes. Optionally
    served from short-TTL Redis cache when ENABLE_OPTIONS_CACHE is true.
    """
    symbol = (body.symbol or "").strip().upper()
    contracts = [c.strip().upper() for c in (body.contracts or []) if c and c.strip()]
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    if not contracts:
        raise HTTPException(status_code=400, detail="contracts list is required")

    # Optional: return cached quotes (short TTL)
    cached = _get_options_quotes_cached(symbol, contracts)
    if cached is not None:
        return cached

    # Try Alpaca first when credentials are set
    if _alpaca_configured():
        result = _fetch_alpaca_options_quotes(symbol, contracts)
        if result is not None:
            _set_options_quotes_cached(symbol, contracts, result)
            return result

    # Fall back to Tradier: fetch full chain and filter to requested contracts
    try:
        tradier = _get_tradier()
    except HTTPException:
        raise
    try:
        chain_df = tradier.get_all_chains(symbol, max_expirations=8, greeks=True)
    except Exception as e:
        logger.exception("Tradier chain fetch for quotes failed")
        raise HTTPException(status_code=502, detail=f"Failed to fetch options: {e}") from e
    contract_set = set(contracts)
    quotes = []
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if chain_df is not None and not chain_df.empty:
        for _, row in chain_df.iterrows():
            sym = str(row.get("symbol", "")).upper()
            if sym not in contract_set:
                continue
            bid = _json_safe_float(row.get("bid"))
            ask = _json_safe_float(row.get("ask"))
            last = _json_safe_float(row.get("last"))
            mark = None
            if bid is not None and ask is not None:
                mark = _json_safe_float((bid + ask) / 2)
            if mark is None and last is not None:
                mark = last
            try:
                oi = int(row.get("open_interest") or 0)
            except (TypeError, ValueError):
                oi = None
            iv = _json_safe_float(row.get("greek_mid_iv") or row.get("iv"))
            try:
                vol = int(row.get("volume") or 0)
            except (TypeError, ValueError):
                vol = None
            delta = _json_safe_float(row.get("greek_delta") or row.get("delta"))
            gamma = _json_safe_float(row.get("greek_gamma") or row.get("gamma"))
            theta = _json_safe_float(row.get("greek_theta") or row.get("theta"))
            vega = _json_safe_float(row.get("greek_vega") or row.get("vega"))
            rho = _json_safe_float(row.get("greek_rho") or row.get("rho"))
            quotes.append({
                "contract_symbol": sym,
                "bid": bid,
                "ask": ask,
                "mark": mark,
                "last": last,
                "volume": vol,
                "open_interest": oi,
                "implied_vol": iv,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "updated_at": now_iso,
            })
    result = {
        "symbol": symbol,
        "timestamp": now_iso,
        "chain_timestamp": now_iso,
        "total_requested": len(contracts),
        "total_returned": len(quotes),
        "quotes": quotes,
    }
    _set_options_quotes_cached(symbol, contracts, result)
    return result


HISTORY_LOOKBACK_DAYS = 30


def _safe_rank_val(v):
    """JSON-safe number for rank fields (None for NaN/Inf)."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


@router.get("/options-rankings")
async def get_options_rankings(
    symbol: str = Query(..., description="Underlying symbol (e.g. AAPL)"),
    expiry: str | None = Query(None, description="Filter by expiry YYYY-MM-DD"),
    side: str | None = Query(None, description="call or put"),
    mode: str = Query("monitor", description="entry, exit, or monitor"),
    sort: str = Query("composite", description="composite, ml, momentum, value, greeks, etc."),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Return options rankings from Supabase (same data as Edge options-rankings).
    Powers the Options Ranker list and detail view (Ranking Modes, Momentum Framework, GA).
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    if side and side.lower() not in ("call", "put"):
        raise HTTPException(status_code=400, detail="side must be call or put")
    mode = (mode or "monitor").lower()
    if mode not in ("entry", "exit", "monitor"):
        raise HTTPException(status_code=400, detail="mode must be entry, exit, or monitor")

    try:
        from datetime import timedelta
        from src.data.supabase_db import db
    except Exception as e:
        logger.warning("Supabase db unavailable: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Rankings require Supabase (SUPABASE_URL and key).",
        ) from e

    try:
        symbol_id = db.get_symbol_id(symbol)
    except Exception as e:
        logger.warning("Symbol not found %s: %s", symbol, e)
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}") from e

    sort_column_map = {
        "composite": "composite_rank",
        "entry": "entry_rank",
        "exit": "exit_rank",
        "ml": "ml_score",
        "momentum": "momentum_score",
        "value": "value_score",
        "greeks": "greeks_score",
    }
    sort_column = sort_column_map.get(sort, "composite_rank")
    if mode == "entry":
        sort_column = "entry_rank"
    elif mode == "exit":
        sort_column = "exit_rank"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Latest run_at for (symbol, mode) to scope run window
    run_window_start = None
    try:
        latest = (
            db.client.table("options_ranks")
            .select("run_at")
            .eq("underlying_symbol_id", symbol_id)
            .eq("ranking_mode", mode)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
        if latest.data and len(latest.data) > 0:
            run_at_str = latest.data[0].get("run_at")
            if run_at_str:
                run_ts = datetime.fromisoformat(run_at_str.replace("Z", "+00:00")).timestamp()
                run_window_start = (datetime.fromtimestamp(run_ts, tz=timezone.utc) - timedelta(hours=72)).isoformat().replace("+00:00", "Z")
    except Exception:
        pass

    query = (
        db.client.table("options_ranks")
        .select("*")
        .eq("underlying_symbol_id", symbol_id)
        .eq("ranking_mode", mode)
        .gte("expiry", today)
        .order(sort_column, desc=True)
        .order("ml_score", desc=True)
        .limit(limit)
    )
    if sort_column != "ml_score":
        query = query.not_.is_(sort_column, "null")
    if run_window_start:
        query = query.gte("run_at", run_window_start)
    if expiry:
        query = query.eq("expiry", expiry)
    if side:
        query = query.eq("side", side.lower())

    try:
        result = query.execute()
    except Exception as e:
        logger.exception("options_ranks query failed")
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    rows = result.data or []

    # History map for history_avg_mark (optional)
    history_map = {}
    if rows:
        contract_symbols = [r.get("contract_symbol") for r in rows if r.get("contract_symbol")]
        if contract_symbols:
            since = (datetime.now(timezone.utc) - timedelta(days=HISTORY_LOOKBACK_DAYS)).isoformat().replace("+00:00", "Z")
            try:
                hist = (
                    db.client.table("options_price_history")
                    .select("contract_symbol, mark")
                    .in_("contract_symbol", contract_symbols[:500])
                    .gte("snapshot_at", since)
                    .execute()
                )
                for row in hist.data or []:
                    sym = (row.get("contract_symbol") or "").upper()
                    if not sym:
                        continue
                    mark_val = row.get("mark")
                    if sym not in history_map:
                        history_map[sym] = {"count": 0, "sum": 0.0}
                    if isinstance(mark_val, (int, float)) and math.isfinite(mark_val):
                        history_map[sym]["count"] += 1
                        history_map[sym]["sum"] += float(mark_val)
            except Exception:
                pass

    def row_to_rank(row):
        cs = row.get("contract_symbol")
        hist = history_map.get((cs or "").upper(), {}) if cs else {}
        h_count = hist.get("count", 0)
        h_avg = (hist["sum"] / h_count) if h_count else None
        return {
            "id": str(row.get("id", "")),
            "contract_symbol": cs,
            "expiry": row.get("expiry") or "",
            "strike": _safe_rank_val(row.get("strike")) or 0,
            "side": row.get("side") or "call",
            "ml_score": _safe_rank_val(row.get("ml_score")),
            "composite_rank": _safe_rank_val(row.get("composite_rank")),
            "entry_rank": _safe_rank_val(row.get("entry_rank")),
            "exit_rank": _safe_rank_val(row.get("exit_rank")),
            "momentum_score": _safe_rank_val(row.get("momentum_score")),
            "value_score": _safe_rank_val(row.get("value_score")),
            "greeks_score": _safe_rank_val(row.get("greeks_score")),
            "entry_value_score": _safe_rank_val(row.get("entry_value_score")),
            "catalyst_score": _safe_rank_val(row.get("catalyst_score")),
            "profit_protection_score": _safe_rank_val(row.get("profit_protection_score")),
            "deterioration_score": _safe_rank_val(row.get("deterioration_score")),
            "time_urgency_score": _safe_rank_val(row.get("time_urgency_score")),
            "relative_value_score": _safe_rank_val(row.get("relative_value_score")),
            "entry_difficulty_score": _safe_rank_val(row.get("entry_difficulty_score")),
            "ranking_stability_score": _safe_rank_val(row.get("ranking_stability_score")),
            "ranking_mode": row.get("ranking_mode"),
            "implied_vol": _safe_rank_val(row.get("implied_vol")),
            "iv_rank": _safe_rank_val(row.get("iv_rank")),
            "spread_pct": _safe_rank_val(row.get("spread_pct")),
            "delta": _safe_rank_val(row.get("delta")),
            "gamma": _safe_rank_val(row.get("gamma")),
            "theta": _safe_rank_val(row.get("theta")),
            "vega": _safe_rank_val(row.get("vega")),
            "rho": _safe_rank_val(row.get("rho")),
            "open_interest": _safe_rank_val(row.get("open_interest")),
            "volume": _safe_rank_val(row.get("volume")),
            "vol_oi_ratio": _safe_rank_val(row.get("vol_oi_ratio")),
            "liquidity_confidence": _safe_rank_val(row.get("liquidity_confidence")),
            "bid": _safe_rank_val(row.get("bid")),
            "ask": _safe_rank_val(row.get("ask")),
            "mark": _safe_rank_val(row.get("mark")),
            "last_price": _safe_rank_val(row.get("last_price")),
            "price_provider": row.get("price_provider") or "alpaca",
            "oi_provider": row.get("oi_provider") or "alpaca",
            "history_samples": h_count,
            "history_avg_mark": _safe_rank_val(h_avg),
            "history_window_days": HISTORY_LOOKBACK_DAYS if h_count else None,
            "signal_discount": row.get("signal_discount"),
            "signal_runner": row.get("signal_runner"),
            "signal_greeks": row.get("signal_greeks"),
            "signal_buy": row.get("signal_buy"),
            "signals": row.get("signals"),
            "underlying_ret_7d": _safe_rank_val(row.get("underlying_ret_7d")),
            "underlying_vol_7d": _safe_rank_val(row.get("underlying_vol_7d")),
            "underlying_drawdown_7d": _safe_rank_val(row.get("underlying_drawdown_7d")),
            "underlying_gap_count": row.get("underlying_gap_count"),
            "run_at": row.get("run_at") or "",
        }

    ranks = [row_to_rank(r) for r in rows]
    filters = {}
    if expiry:
        filters["expiry"] = expiry
    if side:
        filters["side"] = side.lower()

    return {
        "symbol": symbol,
        "totalRanks": len(ranks),
        "ranks": ranks,
        "mode": mode,
        "filters": filters,
    }
