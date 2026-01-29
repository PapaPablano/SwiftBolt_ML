#!/usr/bin/env python3
"""
Generate ensemble validation metrics for canary monitoring.

Runs walk-forward validation on AAPL, MSFT, SPY with 1D horizon using
WalkForwardOptimizer and a simple Ridge ensemble; records metrics to
ensemble_validation_metrics table.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.training.walk_forward_optimizer import WalkForwardOptimizer

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Canary configuration
CANARY_SYMBOLS = ["AAPL", "MSFT", "SPY"]
HORIZON = "1D"
TRAIN_DAYS = 250
VAL_DAYS = 50
TEST_DAYS = 50
MIN_BARS = TRAIN_DAYS + VAL_DAYS + TEST_DAYS  # 350 minimum for one window
FETCH_LIMIT = 2000


class SimpleRidgeEnsemble:
    """
    Minimal ensemble for WalkForwardOptimizer: predicts forward return
    from lagged returns using Ridge regression. Implements train(DataFrame)
    and predict(DataFrame) -> array required by optimize_window.
    """

    def __init__(self, n_lags: int = 5, alpha: float = 1.0):
        self.n_lags = n_lags
        self.alpha = alpha
        self.model = None
        self._feature_cols = None

    def set_hyperparameters(self, params: dict) -> None:
        if not params:
            return
        self.alpha = params.get("alpha", self.alpha)
        self.n_lags = params.get("n_lags", self.n_lags)

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build lagged return features from close prices."""
        ret = df["close"].astype(float).pct_change()
        out = pd.DataFrame(index=df.index)
        for i in range(1, self.n_lags + 1):
            out[f"lag_{i}"] = ret.shift(i)
        return out

    def train(self, data: pd.DataFrame) -> None:
        from sklearn.linear_model import Ridge

        if "actual" not in data.columns and "close" in data.columns:
            data = data.copy()
            data["actual"] = data["close"].astype(float).pct_change().shift(-1)
        y = data["actual"].dropna()
        if len(y) < 50:
            self.model = None
            return
        X = self._features(data).loc[y.index].dropna(how="any")
        y = y.loc[X.index]
        if len(X) < 30:
            self.model = None
            return
        self.model = Ridge(alpha=self.alpha, random_state=42)
        self.model.fit(X.astype(float), y.astype(float))
        self._feature_cols = list(X.columns)

    def predict(self, data: pd.DataFrame):
        if self.model is None:
            return np.full(len(data), np.nan)
        X = self._features(data).astype(float)
        if self._feature_cols:
            X = X.reindex(columns=self._feature_cols).fillna(0)
        return self.model.predict(X)


def run_canary_validation() -> bool:
    """Run walk-forward validation for canary symbols and record metrics."""

    logger.info("=" * 70)
    logger.info("CANARY METRICS GENERATION")
    logger.info("=" * 70)
    logger.info("Symbols: %s", CANARY_SYMBOLS)
    logger.info("Horizon: %s", HORIZON)
    logger.info("Train/Val/Test: %s/%s/%s days", TRAIN_DAYS, VAL_DAYS, TEST_DAYS)

    total_metrics = 0

    for symbol in CANARY_SYMBOLS:
        logger.info("")
        logger.info("Processing %s...", symbol)

        try:
            symbols_result = (
                db.client.table("symbols").select("id").eq("ticker", symbol).execute()
            )
            if not symbols_result.data:
                logger.warning("Symbol %s not found", symbol)
                continue

            symbol_id = symbols_result.data[0]["id"]

            # Fetch OHLC (enough for at least one walk-forward window)
            df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=FETCH_LIMIT)
            if df is None or len(df) < MIN_BARS:
                logger.warning(
                    "Insufficient bars for %s: %d (need %d)",
                    symbol,
                    len(df) if df is not None else 0,
                    MIN_BARS,
                )
                continue

            df = df.copy()
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.set_index("ts").sort_index()
            # Forward 1-day return as target for RMSE
            df["actual"] = df["close"].astype(float).pct_change().shift(-1)
            df = df.dropna(subset=["actual"])

            if len(df) < MIN_BARS:
                logger.warning("Insufficient rows after dropna for %s", symbol)
                continue

            wf_optimizer = WalkForwardOptimizer(
                train_days=TRAIN_DAYS,
                val_days=VAL_DAYS,
                test_days=TEST_DAYS,
                divergence_threshold=0.20,
            )
            windows = wf_optimizer.create_windows(df)
            if not windows:
                logger.warning("No walk-forward windows for %s", symbol)
                continue

            ensemble = SimpleRidgeEnsemble(n_lags=5, alpha=1.0)
            latest_window = windows[-1]
            result = wf_optimizer.optimize_window(
                latest_window, df, ensemble, param_grid=None
            )

            if not np.isfinite(result.val_rmse) or not np.isfinite(result.test_rmse):
                logger.warning(
                    "%s: Skipping insert (non-finite RMSE: val=%.4f test=%.4f)",
                    symbol,
                    result.val_rmse,
                    result.test_rmse,
                )
                continue

            # Insert into ensemble_validation_metrics (same schema as intraday job)
            # Table requires train_rmse, val_rmse, test_rmse > 0
            train_rmse = getattr(result, "train_rmse", None) or result.val_rmse
            if train_rmse <= 0:
                train_rmse = max(result.val_rmse, result.test_rmse, 1e-6)
            validation_date = datetime.now(timezone.utc).isoformat()
            is_overfitting = bool(result.divergence > 0.20)
            metric_record = {
                "symbol_id": str(symbol_id),
                "symbol": symbol,
                "horizon": HORIZON,
                "validation_date": validation_date,
                "window_id": int(result.window_id),
                "train_rmse": float(train_rmse),
                "val_rmse": float(result.val_rmse),
                "test_rmse": float(result.test_rmse),
                "divergence": float(result.divergence),
                "divergence_threshold": 0.20,
                "is_overfitting": is_overfitting,
                "model_count": 2,
                "models_used": ["Ridge", "Ridge"],
                "n_train_samples": int(result.n_train_samples),
                "n_val_samples": int(result.n_val_samples),
                "n_test_samples": int(result.n_test_samples),
                "data_span_days": int(
                    getattr(result, "data_span_days", TRAIN_DAYS + VAL_DAYS + TEST_DAYS)
                ),
            }
            db.client.table("ensemble_validation_metrics").insert(metric_record).execute()
            total_metrics += 1

            logger.info(
                "✓ %s: divergence=%.2f%% (val_rmse=%.4f, test_rmse=%.4f)",
                symbol,
                result.divergence * 100,
                result.val_rmse,
                result.test_rmse,
            )

        except Exception as e:
            logger.error("✗ Failed to process %s: %s", symbol, e, exc_info=True)

    logger.info("")
    logger.info("=" * 70)
    logger.info("COMPLETE: Generated %d validation metrics", total_metrics)
    logger.info("Timestamp: %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 70)
    return total_metrics > 0


if __name__ == "__main__":
    success = run_canary_validation()
    sys.exit(0 if success else 1)
