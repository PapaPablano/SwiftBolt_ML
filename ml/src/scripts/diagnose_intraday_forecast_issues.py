#!/usr/bin/env python
"""
Diagnose intraday forecast quality issues.

Helps identify why forecasts are generating with minimum confidence (40%)
and missing model_agreement scores.
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from src.data.supabase_db import db
from src.scripts.universe_utils import get_symbol_universe

def diagnose_symbol_forecasts(symbol: str):
    """Diagnose forecast issues for a single symbol."""
    print(f"\n{'='*70}")
    print(f"DIAGNOSING: {symbol}")
    print(f"{'='*70}")

    # Get symbol ID
    symbol_id = db.get_symbol_id(symbol)
    if not symbol_id:
        print(f"❌ Symbol not found in database: {symbol}")
        return

    # Check recent indicator data
    print(f"\n1️⃣  INDICATOR DATA (last 2 hours)")
    try:
        indicators = db.client.table("indicator_values").select(
            "created_at,timeframe,rsi_14,macd,adx,atr_14"
        ).eq("symbol_id", symbol_id).gte(
            "created_at", (datetime.utcnow() - timedelta(hours=2)).isoformat()
        ).order("created_at", desc=True).limit(20).execute()

        if indicators.data:
            timeframes_with_data = set()
            for ind in indicators.data:
                timeframes_with_data.add(ind.get("timeframe"))
                print(f"  ✅ {ind['timeframe']}: {ind['created_at']} (RSI={ind.get('rsi_14')}, MACD={ind.get('macd')})")
            print(f"  ➜ Timeframes with data: {', '.join(sorted(timeframes_with_data))}")
        else:
            print(f"  ❌ No indicators found in last 2 hours")
    except Exception as e:
        print(f"  ⚠️  Error fetching indicators: {e}")

    # Check recent OHLC data by timeframe
    print(f"\n2️⃣  OHLC DATA AVAILABILITY")
    for tf in ["m15", "h1", "h4", "d1"]:
        try:
            ohlc = db.fetch_ohlc_bars(symbol, timeframe=tf, limit=5)
            if len(ohlc) > 0:
                last_ts = ohlc["ts"].iloc[-1] if "ts" in ohlc.columns else "unknown"
                last_close = ohlc["close"].iloc[-1]
                print(f"  ✅ {tf}: {len(ohlc)} bars | Last close: ${last_close:.2f} @ {last_ts}")
            else:
                print(f"  ❌ {tf}: NO DATA")
        except Exception as e:
            print(f"  ⚠️  {tf}: Error - {str(e)[:60]}")

    # Check recent forecasts
    print(f"\n3️⃣  RECENT FORECASTS (ml_forecasts table, last 24h)")
    try:
        forecasts = db.client.table("ml_forecasts").select(
            "horizon,overall_label,confidence,model_agreement,quality_score,run_at"
        ).eq("symbol_id", symbol_id).gte(
            "run_at", (datetime.utcnow() - timedelta(hours=24)).isoformat()
        ).order("run_at", desc=True).limit(10).execute()

        if forecasts.data:
            for fc in forecasts.data:
                conf_pct = float(fc.get("confidence", 0)) * 100
                qa_score = fc.get("quality_score", "N/A")
                agreement = fc.get("model_agreement", "NULL")
                print(f"  📊 {fc['horizon']}: {fc['overall_label'].upper():8} | Conf={conf_pct:5.1f}% | QA={qa_score:>4} | Agree={agreement}")
        else:
            print(f"  ❌ No forecasts found in last 24h")
    except Exception as e:
        print(f"  ⚠️  Error fetching forecasts: {e}")

    # Check intraday forecasts
    print(f"\n4️⃣  INTRADAY FORECASTS (ml_forecasts_intraday, last 24h)")
    try:
        intraday = db.client.table("ml_forecasts_intraday").select(
            "horizon,overall_label,confidence,ensemble_label,run_at"
        ).eq("symbol_id", symbol_id).gte(
            "run_at", (datetime.utcnow() - timedelta(hours=24)).isoformat()
        ).order("run_at", desc=True).limit(10).execute()

        if intraday.data:
            for fc in intraday.data:
                conf_pct = float(fc.get("confidence", 0)) * 100
                ensemble_label = fc.get("ensemble_label", "unknown")
                print(f"  📊 {fc['horizon']}: {fc['overall_label'].upper():8} | Conf={conf_pct:5.1f}% | Ensemble={ensemble_label}")
        else:
            print(f"  ❌ No intraday forecasts found in last 24h")
    except Exception as e:
        print(f"  ⚠️  Error fetching intraday forecasts: {e}")

    # Check training data sufficiency
    print(f"\n5️⃣  TRAINING DATA SUFFICIENCY (for advanced ensemble)")
    try:
        h1_data = db.fetch_ohlc_bars(symbol, timeframe="h1", limit=200)
        if len(h1_data) > 0:
            print(f"  ✅ h1 data: {len(h1_data)} bars (need ~100 for ensemble)")
            if len(h1_data) < 100:
                print(f"     ⚠️  WARNING: Insufficient bars for reliable training!")
        else:
            print(f"  ❌ h1 data: NO DATA")

        d1_data = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=250)
        if len(d1_data) > 0:
            print(f"  ✅ d1 data: {len(d1_data)} bars (need ~200 for advanced ensemble)")
            if len(d1_data) < 200:
                print(f"     ⚠️  WARNING: Insufficient bars for reliable training!")
        else:
            print(f"  ❌ d1 data: NO DATA")
    except Exception as e:
        print(f"  ⚠️  Error checking training data: {e}")


def main():
    """Main diagnostics."""
    print("\n" + "="*70)
    print("INTRADAY FORECAST DIAGNOSTICS")
    print("="*70)

    # Get symbols to diagnose
    try:
        universe = get_symbol_universe()
        symbols = universe.get("symbols", [])[:10]  # First 10 symbols
    except:
        symbols = ["AAPL", "NVDA", "MSFT", "TSLA", "META", "AMD", "CRWD", "GOOGL", "AMZN"]

    print(f"\nDiagnosing {len(symbols)} symbols: {', '.join(symbols)}")

    for symbol in symbols:
        try:
            diagnose_symbol_forecasts(symbol)
        except Exception as e:
            print(f"\n❌ ERROR diagnosing {symbol}: {e}")

    # Summary
    print(f"\n{'='*70}")
    print("DIAGNOSTICS COMPLETE")
    print("="*70)
    print("\nCommon Issues:")
    print("1. ❌ 40% confidence everywhere  → Ensemble failing silently")
    print("2. ❌ NULL model_agreement       → Ensemble models not running")
    print("3. ❌ No indicator data           → Feature extraction not running")
    print("4. ❌ Insufficient OHLC bars      → Training data too short")
    print("\nNext Steps:")
    print("→ Check intraday_forecast_job logs for errors")
    print("→ Verify indicators_snapshot_job ran successfully")
    print("→ Check ensemble model implementations for silent failures")


if __name__ == "__main__":
    main()
