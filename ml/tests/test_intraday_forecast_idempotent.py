"""
Idempotent upsert for intraday forecasts: two calls with same (symbol_id, horizon, created_at_iso)
produce one row and the second payload (synthesis_data) overwrites the first.

Run with SUPABASE_URL and key set; skips if env not set. Cleans up after test.
Recommended: run against staging (or a dedicated test project), not production,
since this test inserts and then deletes a real ml_forecasts_intraday row.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _env_ok():
    """Return (ok, has_url, has_key). No secret values—only booleans—so debug prints can't leak them."""
    has_url = bool(
        os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    )
    has_key = bool(
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    return (has_url and has_key), has_url, has_key


def _skip_reason():
    """Return a clear reason when env is missing (env var names only; no secrets)."""
    ok, has_url, has_key = _env_ok()
    if not has_url:
        return "missing SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL"
    if not has_key:
        return (
            "missing Supabase key: set one of SUPABASE_SERVICE_ROLE_KEY, "
            "SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY, or NEXT_PUBLIC_SUPABASE_ANON_KEY"
        )
    return None


SYMBOL_NOT_FOUND_REASON = (
    "AAPL symbol not found in symbols table (run against staging with seeded symbols)"
)


@pytest.fixture(scope="module")
def symbol_id():
    """Resolve AAPL symbol_id for integration test. Returns uuid or None (test skips on None)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if not _env_ok()[0]:
        return None
    from src.data.supabase_db import db
    row = db.client.table("symbols").select("id").eq("ticker", "AAPL").limit(1).execute()
    if not row.data:
        return None
    return row.data[0]["id"]


def test_upsert_intraday_forecast_idempotent_two_calls_one_row_updated_synthesis_data(symbol_id):
    """Two calls with same (symbol_id, horizon, created_at_iso) yield one row; synthesis_data is second payload."""
    env_skip = _skip_reason()
    if env_skip:
        pytest.skip(env_skip)
    if symbol_id is None:
        pytest.skip(SYMBOL_NOT_FOUND_REASON)

    from src.data.supabase_db import db

    created_at_iso = "2026-02-06T14:00:00.000000Z"  # deterministic for idempotency
    horizon = "15m"
    timeframe = "m15"
    common = {
        "symbol_id": symbol_id,
        "symbol": "AAPL",
        "horizon": horizon,
        "timeframe": timeframe,
        "created_at_iso": created_at_iso,
        "overall_label": "bullish",
        "confidence": 0.65,
        "points": None,
        "target_price": 150.0,
        "current_price": 148.0,
        "supertrend_component": 0.1,
        "sr_component": 0.05,
        "ensemble_component": 0.5,
        "supertrend_direction": "BULLISH",
        "ensemble_label": "Bullish",
        "layers_agreeing": 2,
        "expires_at": "2026-02-06T15:00:00Z",
    }

    synthesis_a = {"ensemble_result": {"xgb_prob": 0.5, "run": 1}}
    synthesis_b = {"ensemble_result": {"xgb_prob": 0.7, "run": 2}}

    id1 = db.upsert_intraday_forecast_idempotent(**common, synthesis_data=synthesis_a)
    assert id1 is not None

    id2 = db.upsert_intraday_forecast_idempotent(**common, synthesis_data=synthesis_b)
    assert id2 is not None
    assert id1 == id2, "same conflict key must return same row id"

    row = (
        db.client.table("ml_forecasts_intraday")
        .select("id,synthesis_data")
        .eq("id", id2)
        .single()
        .execute()
    )
    assert row.data is not None
    data = row.data
    assert data.get("synthesis_data") == synthesis_b, "synthesis_data must be replaced by second call (run 2)"
    assert data["synthesis_data"].get("ensemble_result", {}).get("xgb_prob") == 0.7
    assert data["synthesis_data"].get("ensemble_result", {}).get("run") == 2

    # Cleanup
    db.client.table("ml_forecasts_intraday").delete().eq("id", data["id"]).execute()
