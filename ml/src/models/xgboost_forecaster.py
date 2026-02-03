"""
XGBoost forecaster for binary (bullish/bearish) stock prediction.

Same API as BaselineForecaster: prepare_training_data_binary, train(X,y), predict_batch(X).
Uses XGBClassifier for feature-based direction prediction.
"""

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from xgboost import XGBClassifier

from src.features.temporal_indicators import (
    SIMPLIFIED_FEATURES,
    TemporalFeatureEngineer,
    compute_simplified_features,
)

logger = logging.getLogger(__name__)


class XGBoostForecaster:
    """
    XGBoost binary forecaster (bullish vs bearish).
    API compatible with binary_benchmark and compare_models.
    """

    def __init__(self) -> None:
        self.scaler = RobustScaler()
        self.model = XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            eval_metric="logloss",
        )
        self.feature_columns: list[str] = []
        self.is_trained = False

    def prepare_training_data_binary(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
        sentiment_series: Optional[pd.Series] = None,
        threshold_pct: float = 0.005,
        add_simple_regime: bool = False,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Same signature as BaselineForecaster.prepare_training_data_binary. Returns (X, y) only."""
        from src.models.baseline_forecaster import BaselineForecaster

        base = BaselineForecaster()
        result = base.prepare_training_data_binary(
            df,
            horizon_days=horizon_days,
            sentiment_series=sentiment_series,
            threshold_pct=threshold_pct,
            add_simple_regime=add_simple_regime,
        )
        # Baseline returns (X, y, dates); we expose (X, y) for pipeline_audit / test_regimes_fixed
        X = result[0]
        y = result[1]

        # ===== VERIFICATION CODE (add_verification_patch) =====
        print(f"\n{'='*80}")
        print("FEATURE/TARGET VERIFICATION")
        print(f"{'='*80}")
        print(f"Original df rows: {len(df)}")
        print(f"Final X rows: {len(X)}")
        print(f"Final y rows: {len(y)}")
        print(f"Lengths match: {len(X) == len(y)}")
        print(f"Indices match: {X.index.equals(y.index)}")

        # Check for leakage via correlation (y is "bullish"/"bearish" -> use numeric)
        y_bin = (y == "bullish").astype(int)
        correlations = pd.Series(dtype=float)
        if len(X) > 0 and len(y_bin) > 0:
            correlations = X.corrwith(y_bin).abs().sort_values(ascending=False)
            print(f"\nTop 10 features by correlation with target:")
            for feat, corr in correlations.head(10).items():
                print(f"  {feat:40s}: {corr:.3f}")

            max_corr = correlations.iloc[0] if len(correlations) > 0 else 0.0
            if max_corr > 0.65:
                print(f"\n⚠️  WARNING: Max correlation {max_corr:.3f} suggests possible leakage!")
            elif max_corr > 0.55:
                print(f"\n⚠️  CAUTION: Max correlation {max_corr:.3f} is borderline high")
            else:
                print(f"\n✅ Max correlation {max_corr:.3f} looks reasonable")

        # Target distribution (bullish=1, bearish=0)
        print(f"\nTarget distribution:")
        print(f"  Positive (bullish): {(y == 'bullish').sum()} ({(y == 'bullish').mean()*100:.1f}%)")
        print(f"  Negative (bearish): {(y == 'bearish').sum()} ({(y == 'bearish').mean()*100:.1f}%)")

        # NaN check
        nan_in_X = X.isna().sum().sum()
        nan_in_y = y.isna().sum()
        print(f"\nNaN check:")
        print(f"  NaN in X: {nan_in_X}")
        print(f"  NaN in y: {nan_in_y}")
        if nan_in_X > 0 or nan_in_y > 0:
            print(f"  ❌ ERROR: Found NaN values!")
        else:
            print(f"  ✅ No NaN values")
        print(f"{'='*80}")
        # ===== END VERIFICATION CODE =====

        # Step 3 fix: drop high-correlation features if leakage suspected (>0.60)
        if len(correlations) > 0 and correlations.iloc[0] > 0.60:
            high_corr_features = [
                "bb_lower",
                "bb_upper",
                "supertrend_trend_lag30",
                "historical_volatility_60d",
            ]
            drop_cols = [c for c in high_corr_features if c in X.columns]
            if drop_cols:
                X = X.drop(columns=drop_cols, errors="ignore")
                print(f"Dropped {len(drop_cols)} high-correlation features: {drop_cols}")

        # Fill NaN in X so downstream train/predict don't fail (verification already reported)
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0)

        return X, y

    def train(
        self,
        X: pd.DataFrame,
        y: Any,
        min_samples: Optional[int] = None,
        feature_names: Any = None,
    ) -> None:
        """Train XGBoost on numeric features with early stopping. Encodes bullish=1, bearish=0."""
        if min_samples is not None and len(X) < min_samples:
            raise ValueError(
                f"Insufficient training data: {len(X)} < {min_samples}"
            )
        numeric_cols = [
            c for c in X.columns
            if X[c].dtype in ("float64", "float32", "int64", "int32")
        ]
        if not numeric_cols:
            numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        self.feature_columns = numeric_cols
        X_num = X[numeric_cols].fillna(0)
        X_scaled = self.scaler.fit_transform(X_num)
        y_arr = np.asarray(y).ravel()
        y_bin = np.where(np.asarray(y_arr) == "bullish", 1, 0)
        # Split for early stopping (80% train, 20% val), stratified for balance
        X_tr, X_es, y_tr, y_es = train_test_split(
            X_scaled, y_bin,
            test_size=0.2,
            stratify=y_bin,
            random_state=42,
        )
        logger.info("Training XGBoost with early stopping...")
        self.model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_es, y_es)],
            verbose=False,
        )
        if getattr(self.model, "best_iteration", None) is not None:
            logger.info("Best iteration: %s", self.model.best_iteration)
        self.is_trained = True

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict probability of class 1 (bullish). Returns shape (n_samples,) for P(bullish)."""
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        if isinstance(X, pd.DataFrame):
            cols = [c for c in self.feature_columns if c in X.columns]
            X_num = X[cols].reindex(columns=self.feature_columns).fillna(0)
        else:
            X_num = np.asarray(X)
            if X_num.ndim == 1:
                X_num = X_num.reshape(1, -1)
        X_scaled = self.scaler.transform(X_num)
        return self.model.predict_proba(X_scaled)[:, 1]

    def predict_batch(self, X: Any) -> np.ndarray:
        """Predict labels for batch (bullish/bearish)."""
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        proba = self.predict_proba(X)
        return np.where(proba >= 0.5, "bullish", "bearish")
