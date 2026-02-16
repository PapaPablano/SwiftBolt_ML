import os
from datetime import date, timedelta
import requests


BASE = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")


ROOTS = ["ES", "NQ", "GC", "CL", "ZC", "ZS", "ZW", "HE", "LE", "HG", "SI", "PL", "PA"]


END = date.today().isoformat()
START_DAILY = (date.today() - timedelta(days=365)).isoformat()
START_INTRADAY = (date.today() - timedelta(days=45)).isoformat()


TIMEFRAMES_DAILY = ["1d", "1w"]
TIMEFRAMES_INTRADAY = ["15m", "1h", "4h"]


def fetch(symbol, timeframe, start_date, end_date):
    r = requests.get(
        f"{BASE}/api/v1/futures/bars",
        params={
            "symbol": symbol,
            "mode": "continuous",
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
        },
        timeout=30,
    )
    return r


def test_roots_daily_load():
    for root in ROOTS:
        for tf in TIMEFRAMES_DAILY:
            r = fetch(root, tf, START_DAILY, END)
            assert r.status_code == 200, f"{root} {tf} failed: {r.status_code} {r.text}"
            bars = r.json().get("bars", [])
            assert len(bars) > 10, f"{root} {tf} empty/too small: {len(bars)}"


def test_roots_intraday_load():
    for root in ROOTS:
        for tf in TIMEFRAMES_INTRADAY:
            r = fetch(root, tf, START_INTRADAY, END)
            assert r.status_code == 200, f"{root} {tf} failed: {r.status_code} {r.text}"
            bars = r.json().get("bars", [])
            assert len(bars) > 10, f"{root} {tf} empty/too small: {len(bars)}"


def test_es2_normalization():
    r = fetch("ES2!", "1d", START_DAILY, END)
    assert r.status_code == 200, f"ES2! failed: {r.status_code} {r.text}"
    assert len(r.json().get("bars", [])) > 10
