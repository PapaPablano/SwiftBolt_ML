#!/usr/bin/env python3
"""
Audit script: run a backtest like the frontend (calls backend), then export raw data to CSVs.

Produces:
  - stock_data.csv    : OHLCV bars (same source as worker: yfinance)
  - technical_data.csv: Per-bar indicators from the canonical ML pipeline
                        (`add_technical_features` – same as the /technical-indicators API)
  - trading_data.csv  : Backtest trades from the backend result
  - trade_indicators.csv: Per-trade indicator levels for the selected strategy

Usage:
  python scripts/audit_backtest_data.py --symbol AAPL --timeframe 1D --preset supertrend_ai --output-dir ./audit_out
  python scripts/audit_backtest_data.py --symbol AAPL --timeframe 1h --strategy-id <UUID> --start 2024-02-22 --end 2025-02-22
  python scripts/audit_backtest_data.py --symbol AAPL --timeframe 1D --strategy-name "Supertrend RSI"

Requires: pip install yfinance requests pandas (and python-dotenv if using .env)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# Optional .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import yfinance as yf
except ImportError:
    print("Install yfinance: pip install yfinance", file=sys.stderr)
    sys.exit(1)

import requests

try:
    import pandas as pd
except ImportError:
    print("Install pandas: pip install pandas", file=sys.stderr)
    sys.exit(1)

# Make the ML `src` package importable so we can reuse the canonical technical indicator pipeline.
ML_ROOT = Path(__file__).parent.parent / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from src.features.technical_indicators import add_technical_features


# --- Config (env or defaults) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://cygflaemtmwiwaviclks.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs",
)
FASTAPI_URL = os.environ.get("VITE_API_URL", os.environ.get("API_URL", "http://localhost:8000")).rstrip("/")

# Timeframe: UI uses 1D/1h; worker uses d1/h1
TF_MAP = {"1D": "d1", "1d": "d1", "1H": "h1", "1h": "h1", "4h": "h4", "15m": "m15"}
YF_INTERVAL = {"d1": "1d", "h1": "1h", "h4": "1h", "m15": "15m"}


def resolve_strategy_id_by_name(name: str) -> str | None:
    """Look up a saved strategy by name in strategy_user_strategies (Supabase REST API). Returns id or None."""
    url = f"{SUPABASE_URL}/rest/v1/strategy_user_strategies"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    # Exact match first
    q = quote(f'eq."{name}"')
    r = requests.get(f"{url}?select=id,name&name={q}", headers=headers, timeout=10)
    if not r.ok:
        return None
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0].get("id")
    # Case-insensitive contains (ilike *name*)
    q2 = quote(f'ilike.*{name}*')
    r2 = requests.get(f"{url}?select=id,name&name={q2}", headers=headers, timeout=10)
    if not r2.ok:
        return None
    data2 = r2.json()
    if isinstance(data2, list) and len(data2) > 0:
        return data2[0].get("id")
    return None


def fetch_ohlc_yfinance(symbol: str, start_date: str, end_date: str, timeframe: str) -> list[dict]:
    """Fetch OHLCV bars via yfinance (same source as strategy-backtest-worker)."""
    tf = TF_MAP.get(timeframe, timeframe.lower() if len(timeframe) <= 3 else "d1")
    interval = YF_INTERVAL.get(tf, "1d")
    ticker = yf.Ticker(symbol.upper())
    df = ticker.history(start=start_date, end=end_date, interval=interval, auto_adjust=True)
    if df.empty:
        return []
    rows = []
    for ts, row in df.iterrows():
        t = ts.to_pydatetime()
        date_str = t.strftime("%Y-%m-%d") if interval == "1d" else t.strftime("%Y-%m-%dT%H:%M:%S")
        rows.append({
            "date": date_str,
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        })
    return rows


def compute_indicators(rows: list[dict]) -> list[dict]:
    """
    Compute per-bar indicators using the **canonical ML pipeline**.

    This function mirrors the FastAPI `/technical-indicators` endpoint:
    it builds a DataFrame with [ts, open, high, low, close, volume],
    runs `add_technical_features`, then returns a list of dicts where
    each dict contains:

      - `date` (string, YYYY-MM-DD or ISO, matching the input `rows`)
      - `close` (for convenience when auditing)
      - all indicator columns produced by `add_technical_features`,
        i.e. every non-base column not in {ts, open, high, low, close, volume}.
    """
    if not rows:
        return []

    df = pd.DataFrame(rows)
    if "date" not in df.columns:
        raise ValueError("Expected 'date' key in OHLC rows")

    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns in rows: {sorted(missing)}")

    # `add_technical_features` expects a `ts` timestamp column
    df["ts"] = pd.to_datetime(df["date"])

    df_with = add_technical_features(df)

    base_cols = {"ts", "open", "high", "low", "close", "volume"}
    indicator_cols = [c for c in df_with.columns if c not in base_cols]

    out_df = df_with.copy()
    out_df["date"] = df["date"]

    ordered_cols: list[str] = ["date", "close"]
    for col in indicator_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)

    out_df = out_df[ordered_cols]

    records: list[dict] = []
    for rec in out_df.to_dict(orient="records"):
        clean: dict = {}
        for k, v in rec.items():
            if hasattr(v, "item"):
                v = v.item()
            clean[k] = v
        records.append(clean)

    return records


def _fetch_strategy_config(strategy_id: str) -> dict | None:
    """
    Fetch saved strategy config (builder strategy) from Supabase by id.

    Returns the `config` JSON or None if not found / on error.
    """
    url = f"{SUPABASE_URL}/rest/v1/strategy_user_strategies"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(f"{url}?select=config&id=eq.{strategy_id}", headers=headers, timeout=10)
    except Exception:
        return None
    if not r.ok:
        return None
    data = r.json()
    if isinstance(data, list) and data:
        cfg = data[0].get("config")
        return cfg if isinstance(cfg, dict) else None
    return None


def _condition_type_to_columns(cond_type: str, params: dict, tech_cols: set[str]) -> list[str]:
    """
    Map a Strategy Builder ConditionType + params into one or more indicator
    column names from the technical feature DataFrame.
    """
    cols: list[str] = []
    t = cond_type.strip()

    def add_if_present(name: str) -> None:
        if name in tech_cols and name not in cols:
            cols.append(name)

    if t == "rsi":
        add_if_present("rsi_14")
    elif t == "macd":
        add_if_present("macd")
    elif t == "macd_signal":
        add_if_present("macd_signal")
    elif t == "macd_hist":
        add_if_present("macd_hist")
    elif t == "stochastic":
        add_if_present("stoch_k")
        add_if_present("stoch_d")
    elif t == "kdj_k":
        add_if_present("kdj_k")
    elif t == "kdj_d":
        add_if_present("kdj_d")
    elif t == "kdj_j":
        add_if_present("kdj_j")
    elif t == "mfi":
        add_if_present("mfi_14")
        add_if_present("mfi")
    elif t == "williams_r":
        add_if_present("williams_r")
    elif t == "cci":
        add_if_present("cci")
    elif t == "returns_1d":
        add_if_present("returns_1d")
    elif t == "returns_5d":
        add_if_present("returns_5d")
    elif t == "returns_20d":
        add_if_present("returns_20d")
    elif t == "sma":
        period = int(params.get("period", 20))
        add_if_present(f"sma_{period}")
    elif t == "ema":
        period = int(params.get("period", 12))
        add_if_present(f"ema_{period}")
    elif t == "sma_cross":
        fast = int(params.get("fastPeriod", 10))
        slow = int(params.get("slowPeriod", 50))
        add_if_present(f"sma_{fast}")
        add_if_present(f"sma_{slow}")
    elif t == "ema_cross":
        fast = int(params.get("fastPeriod", 12))
        slow = int(params.get("slowPeriod", 26))
        add_if_present(f"ema_{fast}")
        add_if_present(f"ema_{slow}")
    elif t == "adx":
        add_if_present("adx")
        add_if_present("adx_normalized")
    elif t == "plus_di":
        add_if_present("plus_di")
    elif t == "minus_di":
        add_if_present("minus_di")
    elif t == "price_above_sma":
        period = int(params.get("period", 20))
        add_if_present(f"sma_{period}")
        add_if_present("close")
    elif t == "price_above_ema":
        period = int(params.get("period", 12))
        add_if_present(f"ema_{period}")
        add_if_present("close")
    elif t == "price_vs_sma20":
        add_if_present("price_vs_sma20")
    elif t == "price_vs_sma50":
        add_if_present("price_vs_sma50")
    elif t in ("bb", "bb_upper", "bb_lower"):
        add_if_present("bb_upper")
        add_if_present("bb_middle")
        add_if_present("bb_lower")
    elif t == "atr":
        add_if_present("atr_14")
        add_if_present("atr_normalized")
    elif t == "volatility_20d":
        add_if_present("volatility_20d")
    elif t == "supertrend_factor":
        add_if_present("supertrend_factor")
        add_if_present("supertrend_adaptive_factor")
    elif t == "supertrend_trend":
        add_if_present("supertrend_trend")
    elif t == "supertrend_signal":
        add_if_present("supertrend_signal")
    elif t == "close":
        add_if_present("close")
    elif t == "volume":
        add_if_present("volume_ratio")
        add_if_present("obv")
    elif t == "volume_ratio":
        add_if_present("volume_ratio")
    elif t == "obv":
        add_if_present("obv")
        add_if_present("obv_sma")
    # price_breakout, volume_spike, ml_signal do not have direct indicator columns here.
    return cols


def _determine_strategy_indicators(args: argparse.Namespace, tech_fieldnames: list[str]) -> list[str]:
    """
    Determine which indicator columns are relevant for the selected strategy.
    """
    tech_cols = set(tech_fieldnames)
    selected: set[str] = set()

    strategy_config: dict | None = None
    if getattr(args, "strategy_id", None):
        strategy_config = _fetch_strategy_config(args.strategy_id)

    if strategy_config:
        for key in ("entryConditions", "exitConditions"):
            conds = strategy_config.get(key) or []
            if isinstance(conds, list):
                for cond in conds:
                    if not isinstance(cond, dict):
                        continue
                    ctype = cond.get("type")
                    if not isinstance(ctype, str):
                        continue
                    params = cond.get("params") or {}
                    cols = _condition_type_to_columns(ctype, params, tech_cols)
                    selected.update(cols)

    if not selected and getattr(args, "preset", None):
        preset = args.preset
        if preset == "supertrend_ai":
            for name in [
                "supertrend_trend",
                "supertrend_signal",
                "supertrend_factor",
                "supertrend_value",
                "rsi_14",
                "adx",
                "plus_di",
                "minus_di",
            ]:
                if name in tech_cols:
                    selected.add(name)
        elif preset == "sma_crossover":
            for name in ["sma_10", "sma_50", "price_vs_sma20", "price_vs_sma50"]:
                if name in tech_cols:
                    selected.add(name)
        elif preset == "buy_and_hold":
            for name in ["returns_1d", "volatility_20d"]:
                if name in tech_cols:
                    selected.add(name)

    if "close" in tech_cols:
        selected.add("close")

    return sorted(selected)


def _lookup_indicator_row_by_date(tech_by_date: dict, raw_date: str) -> dict | None:
    """
    Look up an indicator row by date string, trying both full timestamp and date-only forms.
    """
    s = str(raw_date)
    if s in tech_by_date:
        return tech_by_date[s]
    day = s.split("T")[0]
    return tech_by_date.get(day)


def merge_trade_indicator_levels(
    trades: list[dict],
    tech_rows: list[dict],
    indicator_cols: list[str],
) -> list[dict]:
    """
    Join per-trade executions with the selected indicator values at those times.

    Returns a new list of trade dicts with indicator fields merged in so the
    caller can write a single combined CSV (trades + indicators).
    """
    if not trades or not tech_rows or not indicator_cols:
        return trades

    tech_by_date: dict[str, dict] = {}
    for row in tech_rows:
        d = str(row.get("date", ""))
        if d:
            tech_by_date[d] = row

    sample = trades[0]
    merged: list[dict] = []

    # Worker-style round-trip trades
    if "entry_date" in sample and "exit_date" in sample:
        for t in trades:
            entry_date = t.get("entry_date")
            exit_date = t.get("exit_date")
            entry_row = _lookup_indicator_row_by_date(tech_by_date, entry_date) if entry_date else None
            exit_row = _lookup_indicator_row_by_date(tech_by_date, exit_date) if exit_date else None
            out = dict(t)  # start with original trade dict
            for col in indicator_cols:
                out[f"entry_{col}"] = None if entry_row is None else entry_row.get(col)
                out[f"exit_{col}"] = None if exit_row is None else exit_row.get(col)
            merged.append(out)
        return merged

    # FastAPI action-style trades (one row per action)
    if "date" in sample:
        for t in trades:
            date_val = t.get("date")
            row = _lookup_indicator_row_by_date(tech_by_date, date_val) if date_val else None
            out = dict(t)
            for col in indicator_cols:
                out[f"ind_{col}"] = None if row is None else row.get(col)
            merged.append(out)
        return merged

    # Unknown schema; return trades unchanged
    return trades


def run_backtest_via_supabase(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str,
    strategy_id: str | None = None,
    preset: str | None = None,
    timeout_poll_sec: int = 60,
) -> dict | None:
    """POST backtest-strategy, poll until completed, return result (same flow as frontend)."""
    url = f"{SUPABASE_URL}/functions/v1/backtest-strategy"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    body = {
        "symbol": symbol,
        "startDate": start_date,
        "endDate": end_date,
        "timeframe": TF_MAP.get(timeframe, timeframe) if len(timeframe) <= 3 else timeframe,
        "initialCapital": 10000,
    }
    if strategy_id:
        body["strategy_id"] = strategy_id
    elif preset:
        body["strategy"] = preset
    else:
        print("Need --strategy-id or --preset", file=sys.stderr)
        return None

    r = requests.post(url, json=body, headers=headers, timeout=30)
    if not r.ok:
        print(f"Backtest POST failed: {r.status_code} {r.text}", file=sys.stderr)
        return None
    data = r.json()
    job_id = data.get("job_id")
    if not job_id:
        print("No job_id in response", file=sys.stderr)
        return None

    for _ in range(timeout_poll_sec):
        time.sleep(1.5)
        r2 = requests.get(f"{url}?id={job_id}", headers=headers, timeout=10)
        if not r2.ok:
            continue
        payload = r2.json()
        status = payload.get("status")
        if status == "completed" and payload.get("result"):
            return payload["result"]
        if status == "failed":
            print(f"Job failed: {payload.get('error', 'unknown')}", file=sys.stderr)
            return None

    print("Backtest job timed out", file=sys.stderr)
    return None


def run_backtest_via_fastapi(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str,
    preset: str,
) -> dict | None:
    """Fallback: POST FastAPI /api/v1/backtest-strategy (preset only)."""
    url = f"{FASTAPI_URL}/api/v1/backtest-strategy"
    body = {
        "symbol": symbol,
        "strategy": preset,
        "startDate": start_date,
        "endDate": end_date,
        "timeframe": TF_MAP.get(timeframe, "d1"),
        "initialCapital": 10000,
    }
    r = requests.post(url, json=body, timeout=90)
    if not r.ok:
        print(f"FastAPI backtest failed: {r.status_code} {r.text}", file=sys.stderr)
        return None
    data = r.json()
    # Normalize to worker-style keys for trading_data.csv
    trades = data.get("trades") or []
    return {
        "metrics": data.get("metrics") or {},
        "trades": trades,
        "equity_curve": data.get("equityCurve") or [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit backtest: fetch OHLC + indicators, run backtest, export CSVs")
    ap.add_argument("--symbol", default="AAPL", help="Symbol (default AAPL)")
    ap.add_argument("--timeframe", default="1D", choices=["1D", "1d", "1H", "1h", "4h", "15m"], help="1D or 1h (default 1D)")
    ap.add_argument("--preset", choices=["supertrend_ai", "sma_crossover", "buy_and_hold"], help="Preset strategy (if no strategy-id/name)")
    ap.add_argument("--strategy-id", help="UUID of saved strategy (builder strategy)")
    ap.add_argument("--strategy-name", help="Name of saved strategy; script looks it up in DB (e.g. \"Supertrend RSI\")")
    ap.add_argument("--start", help="Start date YYYY-MM-DD (default: 1 year ago)")
    ap.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--output-dir", default="./audit_backtest_output", help="Directory for CSVs")
    ap.add_argument("--use-fastapi", action="store_true", help="Use FastAPI backtest instead of Supabase (preset only)")
    args = ap.parse_args()

    if not args.strategy_id and not args.preset and not args.strategy_name:
        ap.error("Provide --strategy-id, --strategy-name, or --preset")
    if args.use_fastapi and not args.preset:
        ap.error("--use-fastapi requires --preset")

    # Resolve --strategy-name to strategy_id via Supabase
    if args.strategy_name and not args.strategy_id:
        print(f"Looking up strategy by name: {args.strategy_name!r}")
        args.strategy_id = resolve_strategy_id_by_name(args.strategy_name.strip())
        if not args.strategy_id:
            print(f"No saved strategy found with name {args.strategy_name!r}", file=sys.stderr)
            print("List strategies in Supabase (strategy_user_strategies) or use --strategy-id <UUID>", file=sys.stderr)
            return 1
        print(f"Resolved to strategy_id: {args.strategy_id}")

    end = args.end or datetime.now().strftime("%Y-%m-%d")
    if args.start:
        start = args.start
    else:
        from datetime import timedelta
        end_d = datetime.strptime(end, "%Y-%m-%d")
        start_d = end_d - timedelta(days=365)
        start = start_d.strftime("%Y-%m-%d")

    symbol = args.symbol.upper()
    tf = args.timeframe
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching OHLC: {symbol} {start} -> {end} {tf}")
    ohlc = fetch_ohlc_yfinance(symbol, start, end, tf)
    if not ohlc:
        print("No OHLC data from yfinance", file=sys.stderr)
        return 1

    stock_path = out_dir / "stock_data.csv"
    with open(stock_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
        w.writeheader()
        w.writerows(ohlc)
    print(f"Wrote {len(ohlc)} rows -> {stock_path}")

    print("Computing indicators (canonical ML pipeline)")
    tech = compute_indicators(ohlc)
    tech_path = out_dir / "technical_data.csv"
    with open(tech_path, "w", newline="") as f:
        if tech:
            fieldnames = list(tech[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in tech:
                w.writerow({k: ("" if v is None else v) for k, v in row.items()})
        else:
            w = csv.DictWriter(f, fieldnames=["date", "close"])
            w.writeheader()
    print(f"Wrote {len(tech)} rows -> {tech_path}")

    print("Running backtest via backend...")
    if args.use_fastapi:
        result = run_backtest_via_fastapi(symbol, start, end, tf, args.preset)
    else:
        result = run_backtest_via_supabase(
            symbol, start, end, tf,
            strategy_id=args.strategy_id,
            preset=args.preset,
        )
    if not result:
        print("Backtest failed; trading_data.csv will be empty", file=sys.stderr)
        trades = []
    else:
        trades = result.get("trades") or []

    # Worker returns entry_date, exit_date, entry_price, exit_price, pnl, pnl_pct; FastAPI may use different keys
    trade_path = out_dir / "trading_data.csv"
    if trades:
        # Merge in indicator levels for the selected strategy so we have a single
        # combined CSV: trade data + indicator context.
        strategy_indicators = _determine_strategy_indicators(args, list(tech[0].keys()) if tech else [])
        merged_trades = merge_trade_indicator_levels(trades, tech, strategy_indicators)

        sample = merged_trades[0]
        fn = list(sample.keys()) if isinstance(sample, dict) else ["entry_date", "exit_date", "entry_price", "exit_price", "pnl", "pnl_pct"]
        with open(trade_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fn, extrasaction="ignore")
            w.writeheader()
            for t in merged_trades:
                w.writerow(t if isinstance(t, dict) else {})
        print(f"Wrote {len(trades)} trades -> {trade_path}")
    else:
        with open(trade_path, "w", newline="") as f:
            f.write("entry_date,exit_date,entry_price,exit_price,pnl,pnl_pct\n")
        print(f"No trades -> {trade_path}")

    # Dump strategy config when using a builder strategy so you can see exactly
    # which entry/exit conditions the worker used (and compare to executed data).
    if getattr(args, "strategy_id", None):
        import json
        cfg = _fetch_strategy_config(args.strategy_id)
        if cfg:
            config_path = out_dir / "strategy_config.json"
            with open(config_path, "w") as f:
                json.dump(cfg, f, indent=2)
            print(f"Wrote strategy config -> {config_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
