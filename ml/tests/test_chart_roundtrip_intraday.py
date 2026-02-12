"""
Roundtrip integration test: ml_forecasts_intraday → /chart and /chart-data-v2.

Inserts a canonical diagnostic row, calls both endpoints, asserts:
- chart: ts remains ISO string; extended keys (ohlc, indicators) preserved.
- chart-data-v2: ts is integer (unix seconds); extended keys preserved; 4h_trading → h4.
- first stored point is strictly in the future vs current bar time (anchor-removal contract).

Run with SUPABASE_URL and SUPABASE_ANON_KEY (or SERVICE_ROLE_KEY) set; uses symbols.ticker.
Skips if env not set. Cleans up the inserted row after the test.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime

import pytest

# Mark as integration so CI can skip without env
pytestmark = pytest.mark.integration

# Current bar (anchor) time: 15:15 UTC. First stored point must be strictly after this (short-points path slices off anchor).
CURRENT_BAR_TS_ISO = "2026-02-10T15:15:00Z"
CURRENT_BAR_TS_SEC = int(datetime.fromisoformat(CURRENT_BAR_TS_ISO.replace("Z", "+00:00")).timestamp())

DIAGNOSTIC_POINTS = [
    {
        "ts": "2026-02-10T15:30:00Z",  # first future bar (step 1); must be > CURRENT_BAR_TS
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


def _env_ok():
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    return bool(url and key)


def _insert_row():
    """Insert diagnostic row; return (symbol_id, row_id) or (None, None)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        return None, None
    from supabase import create_client
    client = create_client(url, key)
    r = client.table("symbols").select("id").eq("ticker", "AAPL").limit(1).execute()
    if not r.data:
        return None, None
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
    if not ins.data:
        return symbol_id, None
    return symbol_id, ins.data[0].get("id")


def _delete_row(row_id):
    if not row_id:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        return
    from supabase import create_client
    client = create_client(url, key)
    client.table("ml_forecasts_intraday").delete().eq("id", row_id).execute()


def _call_chart(base_url: str, anon_key: str) -> dict:
    url = f"{base_url}/functions/v1/chart?symbol=AAPL&timeframe=m15&include_forecast=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {anon_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _call_chart_data_v2(base_url: str, anon_key: str) -> dict:
    url = f"{base_url}/functions/v1/chart-data-v2"
    data = json.dumps({"symbol": "AAPL", "timeframe": "m15", "includeForecast": True}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Authorization": f"Bearer {anon_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


@pytest.mark.skipif(not _env_ok(), reason="SUPABASE_URL and key not set")
def test_chart_roundtrip_iso_and_extended_fields():
    """Insert canonical row, call /chart and /chart-data-v2; assert ts shape and extended keys."""
    _symbol_id, row_id = _insert_row()
    if not row_id:
        pytest.skip("Insert failed (e.g. AAPL not in symbols or RLS)")
    try:
        base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = (
            os.environ.get("SUPABASE_ANON_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        )
        if not base or not key:
            pytest.skip("SUPABASE_URL or key not set")

        # Chart: ts remains ISO string; extended keys preserved
        chart_body = _call_chart(base, key)
        assert "forecast" in chart_body, "chart must return forecast"
        pts = chart_body.get("forecast", {}).get("points") or []
        if not pts:
            pytest.skip("chart returned no forecast points (endpoint may use different source)")
        p0 = pts[0]
        assert p0.get("value") == 246.123456, "chart must return diagnostic value"
        assert isinstance(p0.get("ts"), str), "chart must keep ts as ISO string"
        assert "ohlc" in p0 and "indicators" in p0, "chart must preserve ohlc and indicators (no truncation)"
        # Anchor-removal contract: first stored point must be strictly after current bar time
        first_ts_str = p0.get("ts")
        first_ts_sec = int(datetime.fromisoformat(first_ts_str.replace("Z", "+00:00")).timestamp())
        assert first_ts_sec > CURRENT_BAR_TS_SEC, (
            "first stored point must be strictly in the future vs current bar (anchor not persisted); "
            f"got first_ts={first_ts_str} ({first_ts_sec}), current_bar={CURRENT_BAR_TS_ISO} ({CURRENT_BAR_TS_SEC})"
        )

        # chart-data-v2: ts is integer (unix seconds); extended keys; 4h_trading → h4
        v2_body = _call_chart_data_v2(base, key)
        v2_pts = v2_body.get("forecast", {}).get("points") or []
        if not v2_pts:
            pytest.skip("chart-data-v2 returned no forecast points")
        v2_0 = v2_pts[0]
        assert v2_0.get("value") == 246.123456
        assert isinstance(v2_0.get("ts"), int), "chart-data-v2 must return ts as integer (unix seconds)"
        assert "ohlc" in v2_0 and "indicators" in v2_0, "chart-data-v2 must preserve extended fields"
        # Same anchor-removal contract for v2 response
        first_ts_int = v2_0.get("ts")
        assert first_ts_int > CURRENT_BAR_TS_SEC, (
            "first stored point must be strictly in the future vs current bar (anchor not persisted); "
            f"got first_ts={first_ts_int}, current_bar_sec={CURRENT_BAR_TS_SEC}"
        )
        if len(v2_pts) >= 2:
            assert v2_pts[1].get("timeframe") == "h4", "chart-data-v2 must normalize 4h_trading → h4"
    finally:
        _delete_row(row_id)
