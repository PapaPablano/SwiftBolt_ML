"""
Ensemble Forecaster: Random Forest + Gradient Boosting
=====================================================

Combines predictions from two complementary models for improved accuracy.
"""

import logging
from typing import Dict, Generator

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.base import clone
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.preprocessing import RobustScaler
from sklearn.utils.class_weight import compute_sample_weight

logger = logging.getLogger(__name__)

# Walk-forward CV defaults (15m: 4-bar lookahead)
PURGE_GAP = 4
N_SPLITS = 2  # Fewer folds, larger val windows (less noisy metrics)
VAL_SIZE_MIN = 20  # Enforce min val size per fold
MIN_TRAIN_WALK = 50
MIN_FOR_WALK_FORWARD = 90  # need enough for 2 folds + purge

# Label encoding maps (static; no fit required)
_RF_ENCODE = {"bearish": 0, "neutral": 1, "bullish": 2, "Bearish": 0, "Neutral": 1, "Bullish": 2}
_RF_ENCODE.update({-1: 0, 0: 1, 1: 2})
_GB_ENCODE = {"bearish": -1, "neutral": 0, "bullish": 1, "Bearish": -1, "Neutral": 0, "Bullish": 1}
# Numeric pass-through (incl. numpy int64/float64)
for v in (-1, 0, 1):
    _GB_ENCODE[v] = v
    _GB_ENCODE[float(v)] = v
    if hasattr(np, "int64"):
        _GB_ENCODE[np.int64(v)] = v
        _GB_ENCODE[np.float64(v)] = v


def _encode_rf(y: np.ndarray) -> np.ndarray:
    """Encode labels to RF format (0, 1, 2)."""
    out = np.array([_RF_ENCODE.get(x, _RF_ENCODE.get(str(x).lower() if isinstance(x, str) else x, 1)) for x in y])
    return out.astype(int)


def _encode_gb(y: np.ndarray) -> np.ndarray:
    """Encode labels to GB format (-1, 0, 1). Returns float for NaN handling."""
    out = np.array(
        [_GB_ENCODE.get(x, _GB_ENCODE.get(str(x).lower() if isinstance(x, str) else x, np.nan)) for x in y]
    )
    return out


def _time_series_splits(
    n: int,
    purge: int = PURGE_GAP,
    n_splits: int = N_SPLITS,
    min_train: int = MIN_TRAIN_WALK,
    val_size_min: int = VAL_SIZE_MIN,
) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
    """Yield (train_idx, val_idx) for expanding-window CV with purge."""
    val_size = max(val_size_min, (n - min_train - purge) // n_splits)
    for i in range(n_splits):
        train_end = min_train + i * val_size + i * purge
        val_start = train_end + purge
        val_end = min(val_start + val_size, n)
        if val_end <= val_start:
            break
        yield np.arange(0, train_end), np.arange(val_start, val_end)


class EnsembleForecaster:
    """
    Ensemble combining Random Forest and Gradient Boosting.

    Strategy:
    - Train both RF and GB on same data
    - Predict with both models
    - Average probabilities (50/50 initially, tunable)
    - Take argmax for final prediction

    Expected improvement: +5-8% accuracy over single model
    """

    def __init__(
        self,
        horizon: str = "1D",
        symbol_id: str | None = None,
        rf_weight: float | None = None,
        gb_weight: float | None = None,
        use_db_weights: bool = True,
        use_walk_forward: bool = False,
        use_smote_for_gb: bool = True,
    ) -> None:
        """
        Initialize Ensemble Forecaster.

        Args:
            horizon: Forecast horizon ("1D" or "1W")
            rf_weight: Weight for Random Forest predictions (0-1). If None, uses DB.
            gb_weight: Weight for Gradient Boosting predictions (0-1). If None, uses DB.
            use_db_weights: If True and weights are None, fetch from DB.
            use_walk_forward: If True, use expanding-window CV + early stopping for GB.
            use_smote_for_gb: If False, skip SMOTE for GB and use sample_weight (balanced).
                Strong baseline to compare against SMOTE on small data.

        Note: Weights should sum to 1.0
        """
        from src.models.baseline_forecaster import BaselineForecaster
        from src.models.gradient_boosting_forecaster import (
            GradientBoostingForecaster,
        )

        self.horizon = horizon
        self.symbol_id = symbol_id
        self.use_walk_forward = use_walk_forward
        self.use_smote_for_gb = use_smote_for_gb

        # Try to load weights from database if not provided
        if rf_weight is None or gb_weight is None:
            if use_db_weights:
                db_weights = self._load_weights_from_db(
                    horizon=horizon,
                    symbol_id=symbol_id,
                )
                rf_weight = db_weights.get("rf_weight", 0.5)
                gb_weight = db_weights.get("gb_weight", 0.5)
            else:
                rf_weight = 0.5
                gb_weight = 0.5

        # Normalize weights to sum to 1.0
        total = rf_weight + gb_weight
        self.rf_weight = rf_weight / total
        self.gb_weight = gb_weight / total

        self.rf_model = BaselineForecaster()
        if use_walk_forward:
            self.gb_model = GradientBoostingForecaster(
                horizon=horizon,
                early_stopping_rounds=25,
                n_estimators=2000,
                learning_rate=0.03,
            )
        else:
            self.gb_model = GradientBoostingForecaster(horizon=horizon)
        self.scaler = RobustScaler()
        self.rf_model.scaler = self.scaler

        self.is_trained = False
        self.training_stats: Dict = {}
        logger.info(
            "Ensemble initialized: RF weight=%.2f, GB weight=%.2f (horizon=%s)",
            self.rf_weight,
            self.gb_weight,
            horizon,
        )

    def _load_weights_from_db(
        self,
        horizon: str,
        symbol_id: str | None = None,
    ) -> Dict[str, float]:
        """
        Load model weights from database.

        Args:
            horizon: Forecast horizon

        Returns:
            Dict with rf_weight and gb_weight
        """
        try:
            from src.data.supabase_db import db

            if symbol_id:
                row = db.fetch_symbol_model_weights(
                    symbol_id=symbol_id,
                    horizon=horizon,
                )
                if row:
                    try:
                        import os

                        min_samples = int(os.getenv("SYMBOL_WEIGHT_MIN_SAMPLES", "20"))
                    except Exception:
                        min_samples = 20

                    diag = row.get("diagnostics")
                    if isinstance(diag, dict):
                        n = diag.get("n_samples")
                        try:
                            if n is not None and int(n) < min_samples:
                                row = None
                        except Exception:
                            row = None

                if row:
                    rf = row.get("rf_weight")
                    gb = row.get("gb_weight")
                    if rf is not None and gb is not None:
                        logger.info(
                            "Loaded per-symbol weights for %s (%s): RF=%.2f, GB=%.2f",
                            symbol_id,
                            horizon,
                            float(rf),
                            float(gb),
                        )
                        return {
                            "rf_weight": float(rf),
                            "gb_weight": float(gb),
                        }

            result = db.client.rpc("get_model_weights", {"p_horizon": horizon}).execute()

            if result.data and len(result.data) > 0:
                weights = result.data[0]
                logger.info(
                    "Loaded weights from DB for %s: RF=%.2f, GB=%.2f",
                    horizon,
                    weights.get("rf_weight", 0.5),
                    weights.get("gb_weight", 0.5),
                )
                return {
                    "rf_weight": float(weights.get("rf_weight", 0.5)),
                    "gb_weight": float(weights.get("gb_weight", 0.5)),
                }
        except Exception as e:
            logger.warning("Could not load weights from DB: %s. Using defaults.", e)

        return {"rf_weight": 0.5, "gb_weight": 0.5}

    def train(self, features_df: pd.DataFrame, labels_series: pd.Series) -> "EnsembleForecaster":
        """
        Train both RF and GB models.

        Uses time-ordered holdout: last 20% as validation. Imputation, scaling,
        and SMOTE are applied to training data only to avoid leakage.

        Args:
            features_df: Technical indicators DataFrame
            labels_series: Direction labels {-1, 0, 1} or
                {'bearish', 'neutral', 'bullish'}

        Returns:
            self
        """
        logger.info("Training ensemble (%s)...", self.horizon)

        # Drop datetime columns (they cause float() errors in SMOTE)
        numeric_features = features_df.select_dtypes(
            exclude=["datetime64[ns]", "datetimetz", "object"]
        ).copy()

        if len(numeric_features.columns) != len(features_df.columns):
            dropped = set(features_df.columns) - set(numeric_features.columns)
            logger.info("Dropped non-numeric columns for training: %s", dropped)

        if numeric_features.empty or labels_series.empty:
            raise ValueError(
                "Insufficient numeric training data for ensemble training"
            )

        # Replace inf with NaN for imputation
        X = numeric_features.replace([np.inf, -np.inf], np.nan).values
        y = labels_series.values

        n = len(y)
        feature_cols = numeric_features.columns.tolist()
        self.rf_model._label_decode = {0: "bearish", 1: "neutral", 2: "bullish"}
        self.rf_model.feature_columns = feature_cols

        # Walk-forward CV (when enabled and enough data)
        fold_metrics: list[dict] = []
        if self.use_walk_forward and n >= MIN_FOR_WALK_FORWARD:
            from src.models.gradient_boosting_forecaster import GradientBoostingForecaster

            fold_gb = GradientBoostingForecaster(
                horizon=self.horizon,
                early_stopping_rounds=25,
                n_estimators=2000,
                learning_rate=0.03,
            )
            for fold_idx, (train_idx, val_idx) in enumerate(
                _time_series_splits(n, purge=PURGE_GAP, n_splits=N_SPLITS, min_train=MIN_TRAIN_WALK)
            ):
                X_tr, X_va = X[train_idx], X[val_idx]
                y_tr, y_va = y[train_idx], y[val_idx]
                # Log y_val class counts (tiny val may miss classes; macro-F1/bal_acc can swing)
                y_va_counts = pd.Series(y_va).value_counts().to_dict()
                logger.info(
                    "  Fold %d val: n=%d class_counts=%s",
                    fold_idx + 1,
                    len(y_va),
                    y_va_counts,
                )
                # Train-only preprocess
                tr_med = np.nanmedian(X_tr, axis=0)
                tr_med = np.where(np.isfinite(tr_med), tr_med, 0.0)
                X_tr = np.where(np.isnan(X_tr), tr_med, X_tr)
                X_va = np.where(np.isnan(X_va), tr_med, X_va)
                scaler_f = RobustScaler()
                scaler_f.fit(X_tr)
                X_tr_s = scaler_f.transform(X_tr)
                X_va_s = scaler_f.transform(X_va)
                # SMOTE on train only for RF; GB may use sample_weight instead
                min_cls = pd.Series(y_tr).value_counts().min()
                k = min(5, min_cls - 1) if min_cls > 1 else 0
                if k >= 1:
                    sm = SMOTE(random_state=42, k_neighbors=k)
                    X_tr_bal, y_tr_bal = sm.fit_resample(X_tr_s, y_tr)
                else:
                    X_tr_bal, y_tr_bal = X_tr_s, y_tr
                X_tr_bal_raw = scaler_f.inverse_transform(X_tr_bal)
                rf_labels_tr = _encode_rf(y_tr_bal)
                rf_labels_va = _encode_rf(y_va)
                # GB: use SMOTE data or raw + sample_weight
                if self.use_smote_for_gb:
                    gb_labels_tr = pd.Series(_encode_gb(y_tr_bal))
                    gb_X_tr = pd.DataFrame(X_tr_bal_raw, columns=feature_cols)
                    gb_sw = None
                else:
                    gb_labels_tr = pd.Series(_encode_gb(y_tr))
                    gb_X_tr = pd.DataFrame(X_tr, columns=feature_cols)
                    gb_sw = compute_sample_weight("balanced", y_tr)
                gb_labels_va = _encode_gb(y_va)
                gb_va_internal = np.array([{-1: 0, 0: 1, 1: 2}.get(float(x), 0) for x in gb_labels_va])
                # Train RF (temp clone for fold eval only)
                rf_temp = clone(self.rf_model.model)
                rf_temp.fit(X_tr_bal, rf_labels_tr)
                rf_pred = rf_temp.predict(X_va_s)
                # Train GB with eval_set for early stopping
                gb_internal_tr = gb_labels_tr.map({-1: 0, 0: 1, 1: 2, -1.0: 0, 0.0: 1, 1.0: 2})
                if gb_internal_tr.notna().sum() >= 50:
                    fold_gb.train(
                        gb_X_tr,
                        gb_labels_tr,
                        eval_set=(pd.DataFrame(X_va, columns=feature_cols), gb_va_internal),
                        sample_weight=gb_sw,
                    )
                    gb_pred = fold_gb.model.predict(pd.DataFrame(X_va, columns=feature_cols))
                else:
                    gb_pred = np.full(len(y_va), 1)
                # Metrics
                mf1_rf = f1_score(rf_labels_va, rf_pred, average="macro", zero_division=0)
                mf1_gb = f1_score(gb_va_internal, gb_pred, average="macro", zero_division=0)
                ba_rf = balanced_accuracy_score(rf_labels_va, rf_pred)
                ba_gb = balanced_accuracy_score(gb_va_internal, gb_pred)
                fold_metrics.append({"macro_f1_rf": mf1_rf, "macro_f1_gb": mf1_gb, "bal_acc_rf": ba_rf, "bal_acc_gb": ba_gb})
                logger.info(
                    "  Fold %d: RF macro-F1=%.3f bal_acc=%.3f | GB macro-F1=%.3f bal_acc=%.3f",
                    fold_idx + 1, mf1_rf, ba_rf, mf1_gb, ba_gb,
                )
            if fold_metrics:
                mean_mf1_rf = np.mean([m["macro_f1_rf"] for m in fold_metrics])
                mean_mf1_gb = np.mean([m["macro_f1_gb"] for m in fold_metrics])
                mean_ba_rf = np.mean([m["bal_acc_rf"] for m in fold_metrics])
                mean_ba_gb = np.mean([m["bal_acc_gb"] for m in fold_metrics])
                std_mf1 = np.std([m["macro_f1_gb"] for m in fold_metrics])
                std_ba = np.std([m["bal_acc_gb"] for m in fold_metrics])
                logger.info(
                    "  Walk-forward mean±std: RF macro-F1=%.3f bal_acc=%.3f | GB macro-F1=%.3f±%.3f bal_acc=%.3f±%.3f",
                    mean_mf1_rf, mean_ba_rf, mean_mf1_gb, std_mf1, mean_ba_gb, std_ba,
                )

        MIN_FOR_HOLDOUT = 60  # need enough for train+val; else skip split/SMOTE/holdout
        if n < MIN_FOR_HOLDOUT:
            logger.warning(
                "Insufficient data for holdout (n=%d < %d): training on full data, no SMOTE, no holdout metrics",
                n,
                MIN_FOR_HOLDOUT,
            )
            X_train, X_val = X, np.empty((0, X.shape[1]))
            y_train, y_val = y, np.array([])
            use_holdout = False
        else:
            val_n = max(30, int(0.2 * n))
            split = n - val_n
            X_train, X_val = X[:split], X[split:]
            y_train, y_val = y[:split], y[split:]
            use_holdout = True

        # Impute using TRAIN medians only (no leakage)
        train_medians = np.nanmedian(X_train, axis=0)
        train_medians = np.where(np.isfinite(train_medians), train_medians, 0.0)
        X_train = np.where(np.isnan(X_train), train_medians, X_train)
        X_val = np.where(np.isnan(X_val), train_medians, X_val)

        # Scale using TRAIN only
        self.scaler.fit(X_train)
        X_train_s = self.scaler.transform(X_train)
        X_val_s = self.scaler.transform(X_val) if len(X_val) > 0 else None

        # SMOTE on TRAIN only (never on validation); skip when < MIN_FOR_HOLDOUT
        min_class_count = pd.Series(y_train).value_counts().min()
        k_neighbors = min(5, min_class_count - 1) if min_class_count > 1 else 0

        if use_holdout and k_neighbors >= 1:
            smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
            X_train_bal_s, y_train_bal = smote.fit_resample(X_train_s, y_train)
            logger.info(
                "Class distribution after SMOTE (train): %s",
                pd.Series(y_train_bal).value_counts().to_dict(),
            )
        else:
            if not use_holdout:
                logger.debug("Skipping SMOTE: insufficient data for holdout (n=%d)", n)
            else:
                logger.warning("Skipping SMOTE: minority class too small (%d samples)", min_class_count)
            X_train_bal_s, y_train_bal = X_train_s, y_train

        # Reconstruct unscaled train for GB (GB expects raw features)
        X_train_bal = self.scaler.inverse_transform(X_train_bal_s)

        self.rf_model._label_decode = {0: "bearish", 1: "neutral", 2: "bullish"}
        self.rf_model.feature_columns = feature_cols

        # Encode labels (RF: 0,1,2; GB: -1,0,1)
        rf_labels_train = _encode_rf(y_train_bal)
        rf_labels_val = _encode_rf(y_val)
        if self.use_smote_for_gb:
            gb_labels_train = pd.Series(_encode_gb(y_train_bal))
            gb_X_train = pd.DataFrame(X_train_bal, columns=feature_cols)
            gb_sample_weight = None
        else:
            gb_labels_train = pd.Series(_encode_gb(y_train))
            gb_X_train = pd.DataFrame(X_train, columns=feature_cols)
            gb_sample_weight = compute_sample_weight("balanced", y_train)
        gb_labels_val = _encode_gb(y_val)

        # Train RF on balanced train
        self.rf_model.model.fit(X_train_bal_s, rf_labels_train)
        self.rf_model.is_trained = True

        # Holdout metrics (RF) - macro-F1, balanced_accuracy, accuracy
        if use_holdout and len(y_val) > 0:
            val_pred_rf = self.rf_model.model.predict(X_val_s)
            rf_holdout = accuracy_score(rf_labels_val, val_pred_rf)
            rf_macro_f1 = f1_score(rf_labels_val, val_pred_rf, average="macro", zero_division=0)
            rf_bal_acc = balanced_accuracy_score(rf_labels_val, val_pred_rf)
            logger.info(
                "  RF trained (holdout: acc=%.3f macro-F1=%.3f bal_acc=%.3f)",
                rf_holdout, rf_macro_f1, rf_bal_acc,
            )
        else:
            rf_holdout = rf_macro_f1 = rf_bal_acc = 0.0
            logger.info("  RF trained (no holdout; n=%d)", n)

        # Train GB on balanced train (unscaled; GB does its own imputation)
        # Map -1/0/1 (int or float) to internal 0/1/2 for valid count
        _to_internal = {-1: 0, 0: 1, 1: 2, -1.0: 0, 0.0: 1, 1.0: 2}
        gb_internal = gb_labels_train.map(_to_internal)
        n_valid_for_gb = int(gb_internal.notna().sum())
        min_required_samples_for_gb = 50
        if n_valid_for_gb >= min_required_samples_for_gb:
            try:
                eval_set = None
                if use_holdout and len(y_val) > 0 and self.gb_model.early_stopping_rounds is not None:
                    gb_va_internal = np.array([{-1: 0, 0: 1, 1: 2}.get(float(x), 0) for x in gb_labels_val])
                    eval_set = (pd.DataFrame(X_val, columns=feature_cols), gb_va_internal)
                self.gb_model.train(
                    gb_X_train,
                    gb_labels_train,
                    eval_set=eval_set,
                    sample_weight=gb_sample_weight,
                )
                # GB holdout: predict on val (skip when insufficient data)
                if use_holdout and len(y_val) > 0:
                    gb_val_df = pd.DataFrame(X_val, columns=feature_cols)
                    gb_val_pred = self.gb_model.predict_batch(gb_val_df)
                    gb_pred_internal = np.array(
                        [{"bearish": 0, "neutral": 1, "bullish": 2}.get(str(p).lower(), 1) for p in gb_val_pred["prediction"]]
                    )
                    gb_true_internal = np.array([{-1: 0, 0: 1, 1: 2}.get(float(x), np.nan) for x in gb_labels_val])
                    valid = ~np.isnan(gb_true_internal)
                    gb_holdout = (
                        accuracy_score(gb_true_internal[valid].astype(int), gb_pred_internal[valid])
                        if valid.sum() > 0
                        else 0.0
                    )
                    gb_macro_f1 = f1_score(gb_true_internal[valid].astype(int), gb_pred_internal[valid], average="macro", zero_division=0) if valid.sum() > 0 else 0.0
                    gb_bal_acc = balanced_accuracy_score(gb_true_internal[valid].astype(int), gb_pred_internal[valid]) if valid.sum() > 0 else 0.0
                    best_iter = self.gb_model.training_stats.get("best_iteration")
                    logger.info(
                        "  GB trained (holdout: acc=%.3f macro-F1=%.3f bal_acc=%.3f best_iter=%s)",
                        gb_holdout, gb_macro_f1, gb_bal_acc, best_iter,
                    )
                else:
                    gb_holdout = gb_macro_f1 = gb_bal_acc = 0.0
                    logger.info("  GB trained (no holdout; n=%d)", n)
                gb_accuracy = gb_holdout
            except ValueError as exc:
                logger.warning("  GB training failed: %s. Using RF only.", exc)
                self.rf_weight = 1.0
                self.gb_weight = 0.0
                gb_accuracy = gb_macro_f1 = gb_bal_acc = 0.0
        else:
            logger.warning(
                "  GB skipped: insufficient data (n_valid=%s < %s). Using RF only.",
                n_valid_for_gb,
                min_required_samples_for_gb,
            )
            self.rf_weight = 1.0
            self.gb_weight = 0.0
            gb_accuracy = gb_macro_f1 = gb_bal_acc = 0.0

        self.training_stats = {
            "rf_accuracy": rf_holdout,
            "gb_accuracy": gb_accuracy,
            "rf_holdout": rf_holdout,
            "gb_holdout": gb_accuracy,
            "rf_macro_f1": rf_macro_f1 if use_holdout else 0.0,
            "gb_macro_f1": gb_macro_f1 if use_holdout and n_valid_for_gb >= min_required_samples_for_gb else 0.0,
            "rf_balanced_accuracy": rf_bal_acc if use_holdout else 0.0,
            "gb_balanced_accuracy": gb_bal_acc if use_holdout and n_valid_for_gb >= min_required_samples_for_gb else 0.0,
            "gb_best_iteration": self.gb_model.training_stats.get("best_iteration") if self.gb_model.is_trained else None,
        }
        if fold_metrics:
            self.training_stats["walk_forward_folds"] = fold_metrics
            self.training_stats["wf_mean_macro_f1_gb"] = float(np.mean([m["macro_f1_gb"] for m in fold_metrics]))
            self.training_stats["wf_mean_bal_acc_gb"] = float(np.mean([m["bal_acc_gb"] for m in fold_metrics]))

        self.is_trained = True
        return self

    def predict(self, features_df: pd.DataFrame) -> Dict:
        """
        Predict using ensemble average.

        Args:
            features_df: Technical indicators (1 row)

        Returns:
            Dict with:
            - 'label': Final ensemble prediction
            - 'confidence': Ensemble confidence
            - 'probabilities': Weighted average probabilities
            - 'rf_prediction': Individual RF prediction
            - 'gb_prediction': Individual GB prediction
            - 'agreement': Whether RF and GB agree
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained.")

        # Get RF prediction (BaselineForecaster.predict returns a dict)
        rf_pred = self.rf_model.predict(features_df)
        rf_label = rf_pred["label"]
        rf_confidence = rf_pred["confidence"]
        rf_probs = rf_pred.get("probabilities", {})

        # Get GB prediction (if trained)
        if self.gb_model.is_trained:
            gb_pred = self.gb_model.predict(features_df)
            gb_probs = gb_pred.get("probabilities", {})
        else:
            # RF-only mode
            gb_pred = {"label": "Unknown", "confidence": 0}
            gb_probs = {"bearish": 0, "neutral": 0, "bullish": 0}

        # Weighted average
        ensemble_probs = {
            "bearish": (
                rf_probs.get("bearish", 0) * self.rf_weight
                + gb_probs.get("bearish", 0) * self.gb_weight
            ),
            "neutral": (
                rf_probs.get("neutral", 0) * self.rf_weight
                + gb_probs.get("neutral", 0) * self.gb_weight
            ),
            "bullish": (
                rf_probs.get("bullish", 0) * self.rf_weight
                + gb_probs.get("bullish", 0) * self.gb_weight
            ),
        }

        # Determine final label
        final_label = max(ensemble_probs, key=ensemble_probs.get)
        final_confidence = ensemble_probs[final_label]

        # Check agreement (1.0 = agree, 0.0 = disagree)
        rf_label_str = rf_label.lower() if isinstance(rf_label, str) else rf_label
        gb_label_str = gb_pred.get("label", "Unknown").lower()
        agreement = 1.0 if rf_label_str == gb_label_str else 0.0

        return {
            "label": final_label.capitalize(),
            "confidence": final_confidence,
            "probabilities": ensemble_probs,
            "rf_prediction": rf_label,
            "gb_prediction": gb_pred.get("label", "Unknown"),
            "rf_confidence": rf_confidence,
            "gb_confidence": gb_pred.get("confidence", 0),
            "agreement": agreement,
        }

    def predict_batch(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Batch prediction for multiple rows.

        Args:
            features_df: Technical indicators (multiple rows)

        Returns:
            DataFrame with ensemble predictions
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained.")

        # Get RF batch predictions
        X_scaled = self.scaler.transform(features_df[self.rf_model.feature_columns])
        rf_predictions = self.rf_model.model.predict(X_scaled)
        rf_probabilities = self.rf_model.model.predict_proba(X_scaled)
        rf_classes = self.rf_model.model.classes_

        # Build RF probability dict
        rf_probs = {}
        for i, cls in enumerate(rf_classes):
            rf_probs[cls] = rf_probabilities[:, i]

        # Get GB batch predictions (if trained)
        if self.gb_model.is_trained:
            gb_batch = self.gb_model.predict_batch(features_df)
            gb_bullish = gb_batch["prob_bullish"].values
            gb_bearish = gb_batch["prob_bearish"].values
            gb_neutral = gb_batch["prob_neutral"].values
            gb_labels = gb_batch["prediction"]
        else:
            # RF-only mode
            gb_bullish = np.zeros(len(features_df))
            gb_bearish = np.zeros(len(features_df))
            gb_neutral = np.zeros(len(features_df))
            gb_labels = ["Unknown"] * len(features_df)

        # Weighted average probabilities
        ensemble_bullish = (
            rf_probs.get("bullish", np.zeros(len(features_df))) * self.rf_weight
            + gb_bullish * self.gb_weight
        )
        ensemble_bearish = (
            rf_probs.get("bearish", np.zeros(len(features_df))) * self.rf_weight
            + gb_bearish * self.gb_weight
        )
        ensemble_neutral = (
            rf_probs.get("neutral", np.zeros(len(features_df))) * self.rf_weight
            + gb_neutral * self.gb_weight
        )

        # Determine labels
        ensemble_labels = []
        ensemble_confidences = []
        for i in range(len(features_df)):
            probs = {
                "bullish": ensemble_bullish[i],
                "bearish": ensemble_bearish[i],
                "neutral": ensemble_neutral[i],
            }
            label = max(probs, key=probs.get)
            confidence = probs[label]
            ensemble_labels.append(label.capitalize())
            ensemble_confidences.append(confidence)

        result_df = pd.DataFrame(
            {
                "rf_label": rf_predictions,
                "gb_label": gb_labels,
                "ensemble_label": ensemble_labels,
                "ensemble_confidence": ensemble_confidences,
                "agreement": [
                    1.0 if str(rf).lower() == str(gb).lower() else 0.0
                    for rf, gb in zip(rf_predictions, gb_labels)
                ],
            }
        )

        return result_df

    def compare_models(self, features_df: pd.DataFrame, labels_series: pd.Series) -> Dict:
        """
        Compare accuracy of RF, GB, and Ensemble on held-out data.

        Args:
            features_df: Test features
            labels_series: Test labels

        Returns:
            Dict with accuracy metrics for each model
        """
        reverse_map = {1: "bullish", 0: "neutral", -1: "bearish"}

        # Convert labels to string for comparison
        if labels_series.dtype in [np.int64, np.int32, int]:
            labels_str = labels_series.map(reverse_map)
        else:
            labels_str = labels_series.str.lower()

        # RF predictions (model returns 0,1,2; decode to bearish/neutral/bullish)
        X_scaled = self.rf_model.scaler.transform(features_df[self.rf_model.feature_columns])
        rf_preds_raw = self.rf_model.model.predict(X_scaled)
        decode = getattr(self.rf_model, "_label_decode", {0: "bearish", 1: "neutral", 2: "bullish"})
        rf_preds = pd.Series([decode.get(int(p), "neutral") for p in rf_preds_raw])
        rf_accuracy = (rf_preds.str.lower() == labels_str.values).mean()

        # GB predictions (skip if GB was not trained, e.g. insufficient data)
        if self.gb_model.is_trained:
            gb_preds = self.gb_model.predict_batch(features_df)
            gb_accuracy = (gb_preds["prediction"].str.lower() == labels_str.values).mean()
        else:
            gb_accuracy = 0.0

        # Ensemble predictions
        ensemble_preds = self.predict_batch(features_df)
        ensemble_accuracy = (
            ensemble_preds["ensemble_label"].str.lower() == labels_str.values
        ).mean()

        return {
            "rf_accuracy": rf_accuracy,
            "gb_accuracy": gb_accuracy,
            "ensemble_accuracy": ensemble_accuracy,
            "ensemble_improvement": ensemble_accuracy - max(rf_accuracy, gb_accuracy),
        }

    def save(self, filepath_rf: str, filepath_gb: str) -> None:
        """Save both models."""
        import pickle

        with open(filepath_rf, "wb") as f:
            pickle.dump(
                {
                    "model": self.rf_model.model,
                    "scaler": self.scaler,
                    "feature_columns": self.rf_model.feature_columns,
                },
                f,
            )
        self.gb_model.save(filepath_gb)
        logger.info(f"Ensemble saved (RF: {filepath_rf}, GB: {filepath_gb})")

    def load(self, filepath_rf: str, filepath_gb: str) -> "EnsembleForecaster":
        """Load both models."""
        import pickle

        with open(filepath_rf, "rb") as f:
            rf_data = pickle.load(f)
            self.rf_model.model = rf_data["model"]
            self.scaler = rf_data["scaler"]
            self.rf_model.scaler = self.scaler
            self.rf_model.feature_columns = rf_data["feature_columns"]
            self.rf_model.is_trained = True

        self.gb_model.load(filepath_gb)
        self.is_trained = True
        logger.info(f"Ensemble loaded (RF: {filepath_rf}, GB: {filepath_gb})")
        return self


if __name__ == "__main__":
    print("EnsembleForecaster imported successfully")
