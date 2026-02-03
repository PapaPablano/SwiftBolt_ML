#!/usr/bin/env python3
"""
Identify top features using XGBoost feature importance.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    symbol = "TSLA"
    threshold = 0.008

    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=600)
    except Exception as e:
        print(f"DB error: {e}")
        sys.exit(1)

    if df is None or len(df) < 250:
        print("Insufficient OHLCV data.")
        sys.exit(1)

    from src.models.xgboost_forecaster import XGBoostForecaster

    forecaster = XGBoostForecaster()
    X, y, dates = forecaster.prepare_training_data_binary(
        df,
        horizon_days=1,
        sentiment_series=None,
        threshold_pct=threshold,
        add_simple_regime=True,
    )

    split = int(len(X) * 0.8)
    X_train = X.iloc[:split] if hasattr(X, "iloc") else X[:split]
    y_train = y.iloc[:split] if hasattr(y, "iloc") else y[:split]
    forecaster.train(X_train, y_train)

    importances = forecaster.model.feature_importances_
    feature_names = forecaster.feature_columns

    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances,
    }).sort_values("importance", ascending=False)

    print("\nTop 20 Features:")
    print(importance_df.head(20).to_string(index=False))

    out_dir = Path(__file__).resolve().parent
    csv_path = out_dir / "feature_importance.csv"
    importance_df.to_csv(csv_path, index=False)
    print(f"\nSaved to {csv_path}")

    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 8))
        top = importance_df.head(20)
        plt.barh(top["feature"], top["importance"])
        plt.xlabel("Importance")
        plt.title(f"{symbol} Feature Importance (Top 20)")
        plt.tight_layout()
        fig_path = out_dir / "feature_importance.png"
        plt.savefig(fig_path, dpi=150)
        plt.close()
        print(f"Saved plot to {fig_path}")
    except Exception as e:
        print(f"Plot skipped: {e}")


if __name__ == "__main__":
    main()
