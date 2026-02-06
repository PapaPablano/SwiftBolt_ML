#!/usr/bin/env python3
"""Generate and store daily binary forecasts into Supabase for app charts.

Usage (run from ml/):
    PYTHONPATH=. python scripts/generate_daily_binary_forecasts.py

This will:
  - Loop over a symbol universe
  - For each horizon (1D, 5D, 10D, 20D)
  - Train BinaryForecaster on latest history
  - Write a single up/down forecast per (symbol, horizon, today)

The app can then query the `ml_binary_forecasts` table to overlay predictions on charts.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.data.supabase_db import db
from src.models.binary_forecaster import BinaryForecaster

SYMBOLS = ["AAPL", "MSFT", "SPY", "PG", "NVDA"]
HORIZONS = [1, 5, 10, 20]

TABLE_NAME = "ml_binary_forecasts"


def upsert_forecast_row(row: dict) -> None:
    """Insert or update a single forecast row in Supabase.

    Uses (symbol, forecast_date, horizon_days) as a natural key.
    """
    client = db.client
    # Use PostgREST upsert with conflict target
    client.table(TABLE_NAME).upsert(row, on_conflict=["symbol", "forecast_date", "horizon_days"]).execute()


def generate_forecasts_for_symbol(symbol: str) -> list[dict]:
    symbol = symbol.upper().strip()
    print(f"\n=== Generating forecasts for {symbol} ===")

    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=1000)
    if df is None or len(df) == 0:
        print(f"  ! No OHLC data for {symbol}, skipping")
        return []

    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    if len(df) < 200:
        print(f"  ! Not enough history for {symbol} (have {len(df)}, need >=200), skipping")
        return []

    forecasts: list[dict] = []

    for horizon in HORIZONS:
        try:
            model = BinaryForecaster()
            X, y = model.prepare_training_data(df, horizon_days=horizon)
            if len(X) < 100:
                print(f"  - Horizon {horizon}D: insufficient samples ({len(X)}), skipping")
                continue

            model.train(X, y, min_samples=50)
            pred = model.predict(df, horizon_days=horizon)

            last_ts = df["ts"].iloc[-1]
            if isinstance(last_ts, pd.Timestamp):
                forecast_date = last_ts.to_pydatetime().replace(tzinfo=timezone.utc)
            else:
                forecast_date = datetime.fromisoformat(str(last_ts)).replace(tzinfo=timezone.utc)

            row = {
                "symbol": symbol,
                "forecast_date": forecast_date.isoformat(),
                "horizon_days": horizon,
                "predicted_label": pred["label"],  # 'up' or 'down'
                "confidence": float(pred["confidence"]),
                "prob_up": float(pred["probabilities"]["up"]),
                "prob_down": float(pred["probabilities"]["down"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "binary_forecaster_v1",
            }

            upsert_forecast_row(row)
            forecasts.append(row)

            print(
                f"  - {symbol} {horizon:>2}D: {row['predicted_label']} "
                f"(conf={row['confidence']:.2f}, up={row['prob_up']:.2f}, down={row['prob_down']:.2f})",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! Error generating {horizon}D forecast for {symbol}: {exc}")
            continue

    return forecasts


def main() -> None:
    print("Generating daily binary forecasts for chart overlay...")
    all_rows: list[dict] = []

    for symbol in SYMBOLS:
        rows = generate_forecasts_for_symbol(symbol)
        all_rows.extend(rows)

    print(f"\nDone. Wrote {len(all_rows)} forecasts into {TABLE_NAME}.")


if __name__ == "__main__":
    main()
