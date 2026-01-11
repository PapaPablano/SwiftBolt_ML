"""
Ensemble Forecaster: Random Forest + Gradient Boosting
=====================================================

Combines predictions from two complementary models for improved accuracy.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE

logger = logging.getLogger(__name__)


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
    ) -> None:
        """
        Initialize Ensemble Forecaster.

        Args:
            horizon: Forecast horizon ("1D" or "1W")
            rf_weight: Weight for Random Forest predictions (0-1). If None, uses DB.
            gb_weight: Weight for Gradient Boosting predictions (0-1). If None, uses DB.
            use_db_weights: If True and weights are None, fetch from DB.

        Note: Weights should sum to 1.0
        """
        from src.models.baseline_forecaster import BaselineForecaster
        from src.models.gradient_boosting_forecaster import (
            GradientBoostingForecaster,
        )

        self.horizon = horizon
        self.symbol_id = symbol_id

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
        self.gb_model = GradientBoostingForecaster(horizon=horizon)

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

        Args:
            features_df: Technical indicators DataFrame
            labels_series: Direction labels {-1, 0, 1} or
                {'bearish', 'neutral', 'bullish'}

        Returns:
            self
        """
        logger.info("Training ensemble (%s)...", self.horizon)

        # Drop datetime columns before SMOTE (they cause float() errors)
        numeric_features = features_df.select_dtypes(
            exclude=["datetime64[ns]", "datetimetz", "object"]
        ).copy()

        if len(numeric_features.columns) != len(features_df.columns):
            dropped = set(features_df.columns) - set(numeric_features.columns)
            logger.info("Dropped non-numeric columns for training: %s", dropped)

        # Dynamically set k_neighbors based on smallest class size
        min_class_count = labels_series.value_counts().min()
        k_neighbors = min(5, min_class_count - 1) if min_class_count > 1 else 0

        if k_neighbors < 1:
            # If any class has only 1 sample, skip SMOTE and use original data
            logger.warning("Skipping SMOTE: minority class too small (%d samples)", min_class_count)
            X_balanced, y_balanced = numeric_features.values, labels_series.values
        else:
            smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
            X_balanced, y_balanced = smote.fit_resample(numeric_features, labels_series)

        logger.info(
            "Class distribution after SMOTE: %s",
            pd.Series(y_balanced).value_counts().to_dict(),
        )

        # Train RF (expects string labels)
        rf_labels = pd.Series(y_balanced)
        if rf_labels.dtype in [np.int64, np.int32, int]:
            label_map = {-1: "bearish", 0: "neutral", 1: "bullish"}
            rf_labels = rf_labels.map(label_map)

        self.rf_model.feature_columns = numeric_features.columns.tolist()
        self.rf_model.scaler.fit(X_balanced)
        X_scaled = self.rf_model.scaler.transform(X_balanced)
        self.rf_model.model.fit(X_scaled, rf_labels)
        self.rf_model.is_trained = True
        rf_accuracy = self.rf_model.model.score(X_scaled, rf_labels)
        logger.info("  RF trained (accuracy: %.3f)", rf_accuracy)

        # Train GB (expects numeric labels -1, 0, 1)
        gb_labels = pd.Series(y_balanced)
        if gb_labels.dtype == object:
            reverse_map = {
                "bearish": -1,
                "neutral": 0,
                "bullish": 1,
                "Bearish": -1,
                "Neutral": 0,
                "Bullish": 1,
            }
            gb_labels = gb_labels.map(reverse_map)

        if len(X_balanced) >= 100:
            try:
                self.gb_model.train(
                    pd.DataFrame(X_balanced, columns=features_df.columns),
                    gb_labels,
                )
                gb_accuracy = self.gb_model.training_stats.get("training_accuracy", 0)
                logger.info("  GB trained (accuracy: %.3f)", gb_accuracy)
            except ValueError as exc:
                logger.warning("  GB training failed: %s. Using RF only.", exc)
                self.rf_weight = 1.0
                self.gb_weight = 0.0
                gb_accuracy = 0.0
        else:
            logger.warning(
                "  GB skipped: insufficient data (%s < 100). Using RF only.",
                len(X_balanced),
            )
            self.rf_weight = 1.0
            self.gb_weight = 0.0
            gb_accuracy = 0.0

        self.training_stats = {
            "rf_accuracy": rf_accuracy,
            "gb_accuracy": gb_accuracy,
        }

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

        # Get RF prediction
        rf_label, rf_confidence, rf_proba = self.rf_model.predict(features_df)
        rf_probs = dict(zip(self.rf_model.model.classes_, rf_proba[-1]))

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
        X_scaled = self.rf_model.scaler.transform(features_df[self.rf_model.feature_columns])
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

        # RF predictions
        X_scaled = self.rf_model.scaler.transform(features_df[self.rf_model.feature_columns])
        rf_preds = self.rf_model.model.predict(X_scaled)
        rf_accuracy = (pd.Series(rf_preds).str.lower() == labels_str.values).mean()

        # GB predictions
        gb_preds = self.gb_model.predict_batch(features_df)
        gb_accuracy = (gb_preds["prediction"].str.lower() == labels_str.values).mean()

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
                    "scaler": self.rf_model.scaler,
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
            self.rf_model.scaler = rf_data["scaler"]
            self.rf_model.feature_columns = rf_data["feature_columns"]
            self.rf_model.is_trained = True

        self.gb_model.load(filepath_gb)
        self.is_trained = True
        logger.info(f"Ensemble loaded (RF: {filepath_rf}, GB: {filepath_gb})")
        return self


if __name__ == "__main__":
    print("EnsembleForecaster imported successfully")
