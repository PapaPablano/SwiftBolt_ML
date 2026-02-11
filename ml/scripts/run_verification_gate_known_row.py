#!/usr/bin/env python3
"""
Verification gate: known-row test for chart intraday endpoints.

Inserts a diagnostic row into ml_forecasts_intraday (AAPL/m15) with a distinctive
points payload (value 246.123456, ohlc, indicators, one point with timeframe 4h_trading),
then prints curl commands to call both chart endpoints. Use to confirm:
- At least one endpoint returns points from ml_forecasts_intraday with extended fields.
- No truncation to {ts, value, lower, upper}; ohlc and indicators preserved.
- 4h_trading is normalized to h4 in the response.
- For chart-data-v2: points[].ts is integer (unix seconds).

Usage (from repo root):
  python ml/scripts/run_verification_gate_known_row.py                    # print SQL + curl only
  python ml/scripts/run_verification_gate_known_row.py --call             # call endpoints only (row must exist, e.g. inserted via MCP)
  python ml/scripts/run_verification_gate_known_row.py --insert            # insert via Supabase (use SERVICE_ROLE_KEY in CI/admin; anon may fail under RLS)
  python ml/scripts/run_verification_gate_known_row.py --insert --call     # insert, call, then cleanup
  python ml/scripts/run_verification_gate_known_row.py --insert --cleanup  # insert then delete row (no call)

Insert/cleanup: Use SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) in CI/admin only; anon-key
inserts should fail under RLS in prod. Cleanup runs after successful --call or when --cleanup is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Load .env from cwd, ml/, or repo root so SUPABASE_* are set without exporting
try:
    from dotenv import load_dotenv
    load_dotenv()
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _ml_env = os.path.join(_script_dir, "..", ".env")
    if os.path.isfile(_ml_env):
        load_dotenv(_ml_env)
    _root_env = os.path.join(_script_dir, "..", "..", ".env")
    if os.path.isfile(_root_env):
        load_dotenv(_root_env)
except ImportError:
    pass

# Diagnostic payload from plan: Chart Intraday and Production L1 Writer
DIAGNOSTIC_POINTS = [
    {
        "ts": "2026-02-10T15:30:00Z",
        "value": 246.123456,
        "lower": 244.0,
        "upper": 248.0,
        "timeframe": "m15",
        "step": 1,
        "ohlc": {"open": 245.0, "high": 246.5, "low": 244.5, "close": 246.123456, "volume": 1000},
        "indicators": {"rsi_14": 55.5, "macd": 0.12},
    },
    {
        "ts": "2026-02-10T15:45:00Z",
        "value": 247.0,
        "lower": 245.0,
        "upper": 249.0,
        "timeframe": "4h_trading",
        "step": 2,
        "ohlc": {"open": 246.0, "high": 247.5, "low": 245.5, "close": 247.0, "volume": 1100},
        "indicators": {"rsi_14": 56.0, "macd": 0.13},
    },
]

EXPIRES_AT = "2030-01-01T00:00:00Z"


def get_insert_sql(symbol_id_placeholder: str = "<AAPL_SYMBOL_ID>") -> str:
    points_escaped = json.dumps(DIAGNOSTIC_POINTS).replace("'", "''")
    return f"""
-- 1) Get AAPL symbol_id (run first, then substitute in step 2):
SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1;

-- 2) Insert diagnostic row (replace {symbol_id_placeholder!r} with the UUID from step 1):
INSERT INTO ml_forecasts_intraday (
  symbol_id, symbol, horizon, timeframe, overall_label, confidence,
  target_price, current_price, supertrend_component, sr_component, ensemble_component,
  supertrend_direction, ensemble_label, layers_agreeing, expires_at, points
) VALUES (
  '{symbol_id_placeholder}',
  'AAPL',
  '15m',
  'm15',
  'bullish',
  0.75,
  250.0,
  245.0,
  0.1,
  0.2,
  0.45,
  'BULLISH',
  'bullish',
  3,
  '{EXPIRES_AT}',
  '{points_escaped}'::jsonb
);
"""


def get_curl_commands(base_url: str = "https://<PROJECT_REF>.supabase.co", anon_key: str = "<ANON_KEY>") -> str:
    return f"""
-- 3) Call both chart endpoints (replace base URL and anon key):

# Consolidated chart (ts remains ISO string; forecast.points[0].value === 246.123456, ohlc + indicators present; points[1].timeframe === "h4")
curl -s "{base_url}/functions/v1/chart?symbol=AAPL&timeframe=m15&include_forecast=true" \\
  -H "Authorization: Bearer {anon_key}" \\
  -H "Content-Type: application/json" | jq .

# chart-data-v2 (points[].ts is integer unix seconds; ohlc + indicators preserved; timeframe 4h_trading → h4)
curl -s -X POST "{base_url}/functions/v1/chart-data-v2" \\
  -H "Authorization: Bearer {anon_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"symbol":"AAPL","timeframe":"m15","includeForecast":true}}' | jq .

Pass criteria:
- At least one response contains forecast point with value 246.123456 and keys ohlc, indicators.
- Second point has timeframe "h4" (normalized from 4h_trading).
- For chart-data-v2: points[0].ts is an integer (unix seconds).
"""


def _get_supabase_client():
    """Return (url, key, client) or (None, None, None). Prefer SERVICE_ROLE_KEY for inserts (RLS)."""
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    anon_key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    key = service_key or anon_key
    if not url or not key:
        return None, None, None
    if not service_key and anon_key:
        print("Warning: Use SUPABASE_SERVICE_ROLE_KEY for --insert in CI/admin; anon inserts may fail under RLS.", file=sys.stderr)
    try:
        from supabase import create_client
        return url, key, create_client(url, key)
    except Exception:
        return None, None, None


def run_insert() -> tuple[str, str | None] | None:
    """Insert diagnostic row via Supabase. Returns (symbol_id, row_id) or None. row_id may be None if insert didn't return id."""
    url, key, client = _get_supabase_client()
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) for --insert.", file=sys.stderr)
        return None
    try:
        r = client.table("symbols").select("id").eq("ticker", "AAPL").limit(1).execute()
        if not r.data or len(r.data) == 0:
            print("AAPL not found in symbols table (ticker column).", file=sys.stderr)
            return None
        symbol_id = r.data[0]["id"]
        row = {
            "symbol_id": symbol_id,
            "symbol": "AAPL",
            "horizon": "15m",
            "timeframe": "m15",
            "overall_label": "bullish",
            "confidence": 0.75,
            "target_price": 250.0,
            "current_price": 245.0,
            "supertrend_component": 0.1,
            "sr_component": 0.2,
            "ensemble_component": 0.45,
            "supertrend_direction": "BULLISH",
            "ensemble_label": "bullish",
            "layers_agreeing": 3,
            "expires_at": EXPIRES_AT,
            "points": DIAGNOSTIC_POINTS,
        }
        ins = client.table("ml_forecasts_intraday").insert(row).execute()
        if ins.data:
            row_id = ins.data[0].get("id")
            print(f"Inserted diagnostic row for AAPL (symbol_id={symbol_id}, id={row_id})")
            return (symbol_id, row_id)
    except Exception as e:
        print(f"Insert failed: {e}", file=sys.stderr)
    return None


def run_cleanup(row_id: str) -> bool:
    """Delete the diagnostic row by id. Returns True if deleted or not found."""
    _, _, client = _get_supabase_client()
    if not client:
        return False
    try:
        client.table("ml_forecasts_intraday").delete().eq("id", row_id).execute()
        print(f"Cleanup: deleted diagnostic row id={row_id}", flush=True)
        return True
    except Exception as e:
        print(f"Cleanup failed: {e}", file=sys.stderr)
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Verification gate: known-row test for chart intraday endpoints")
    ap.add_argument("--insert", action="store_true", help="Insert diagnostic row (use SERVICE_ROLE_KEY in CI/admin)")
    ap.add_argument("--call", action="store_true", help="Call both chart endpoints")
    ap.add_argument("--cleanup", action="store_true", help="Delete inserted diagnostic row after run (or with --insert only)")
    ap.add_argument("--base-url", default=os.environ.get("SUPABASE_URL", "https://<PROJECT_REF>.supabase.co"), help="Supabase project URL")
    ap.add_argument("--anon-key", default=os.environ.get("SUPABASE_ANON_KEY", "<ANON_KEY>"), help="Anon key for Edge calls")
    args = ap.parse_args()

    inserted_row_id: str | None = None
    if args.insert:
        print("Inserting diagnostic row...", flush=True)
        out = run_insert()
        if out is None:
            print("Exiting (insert failed or env not set).", file=sys.stderr)
            sys.exit(1)
        _symbol_id, inserted_row_id = out
        print("Insert OK.", flush=True)
    else:
        print("SQL (run in Supabase SQL editor or use --insert with SUPABASE_URL and key in env):")
        print(get_insert_sql())

    print("\nCurl commands:")
    print(get_curl_commands(base_url=args.base_url.rstrip("/"), anon_key=args.anon_key))

    if args.call:
        import urllib.request
        base = args.base_url.rstrip("/")
        auth = f"Bearer {args.anon_key}"
        for name, url in [
            ("chart", f"{base}/functions/v1/chart?symbol=AAPL&timeframe=m15&include_forecast=true"),
            ("chart-data-v2", f"{base}/functions/v1/chart-data-v2"),
        ]:
            req = urllib.request.Request(url, headers={"Authorization": auth, "Content-Type": "application/json"})
            if name == "chart-data-v2":
                req.data = json.dumps({"symbol": "AAPL", "timeframe": "m15", "includeForecast": True}).encode()
                req.method = "POST"
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = json.loads(resp.read().decode())
                print(f"\n--- {name} response (excerpt) ---")
                print(json.dumps(body, indent=2)[:2000])
                if name == "chart" and "forecast" in body and "points" in body["forecast"]:
                    pts = body["forecast"]["points"]
                    if pts and pts[0].get("value") == 246.123456 and "ohlc" in pts[0] and "indicators" in pts[0]:
                        print("[PASS] chart: diagnostic point with ohlc+indicators")
                    else:
                        print("[CHECK] chart: verify forecast.points[0].value=246.123456, ohlc, indicators")
                if name == "chart-data-v2" and "forecast" in body and "points" in body["forecast"]:
                    pts = body["forecast"]["points"]
                    if pts:
                        ts = pts[0].get("ts")
                        print(f"[CHECK] chart-data-v2: points[0].ts is integer (unix) = {isinstance(ts, int) and ts == int(ts)}")
            except Exception as e:
                print(f"[ERROR] {name}: {e}")

    # Remove test footprint: delete diagnostic row after successful run when requested
    if inserted_row_id and (args.cleanup or args.call):
        run_cleanup(inserted_row_id)


if __name__ == "__main__":
    main()
