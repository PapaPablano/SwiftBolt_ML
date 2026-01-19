"""
Gradient Boosting Forecaster for Stock Direction Prediction
============================================================

XGBoost-based classifier for predicting Bullish/Neutral/Bearish direction.
Designed to complement Random Forest in ensemble.
"""

import logging
import os
import pickle
from typing import Dict, List

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)


class GradientBoostingForecaster:
    """
    Gradient Boosting classifier for stock direction prediction.

    Models:
    - XGBoost multiclass classifier
    - 200 trees with shallow depth (max_depth=3)
    - Learning rate: 0.05 (conservative, prevents overfitting)

    Labels (internal encoding for XGBoost - must start from 0):
    - 0 (Bearish): Forward return < -2%
    - 1 (Neutral): Forward return between -2% and +2%
    - 2 (Bullish): Forward return > +2%
    """

    # Internal label encoding (XGBoost requires 0-indexed labels)
    INTERNAL_LABEL_MAP = {0: "Bearish", 1: "Neutral", 2: "Bullish"}
    # External label map (what users provide: -1, 0, 1)
    LABEL_MAP = {-1: "Bearish", 0: "Neutral", 1: "Bullish"}
    REVERSE_LABEL_MAP = {"Bearish": -1, "Neutral": 0, "Bullish": 1}
    # Conversion from external to internal
    EXTERNAL_TO_INTERNAL = {-1: 0, 0: 1, 1: 2}
    INTERNAL_TO_EXTERNAL = {0: -1, 1: 0, 2: 1}

    def __init__(self, horizon: str = "1D", random_state: int = 42) -> None:
        """
        Initialize Gradient Boosting Forecaster.

        Args:
            horizon: Forecast horizon ("1D" for 1 day, "1W" for 1 week)
            random_state: Random seed for reproducibility
        """
        self.horizon = horizon
        self.random_state = random_state
        self.model: XGBClassifier | None = None
        self.is_trained = False
        self.feature_names: List[str] | None = None
        self.training_stats: Dict = {}

    def _build_model(self) -> XGBClassifier:
        """Construct XGBoost model with optimized hyperparameters."""
        tree_method = os.getenv("XGBOOST_TREE_METHOD")
        predictor = os.getenv("XGBOOST_PREDICTOR")
        try:
            n_jobs = int(os.getenv("XGBOOST_N_JOBS", "-1"))
        except Exception:
            n_jobs = -1

        max_bin = os.getenv("XGBOOST_MAX_BIN")
        try:
            max_bin_value = int(max_bin) if max_bin else None
        except Exception:
            max_bin_value = None

        params = {
            "tree_method": tree_method,
            "predictor": predictor,
            "n_jobs": n_jobs,
            "max_bin": max_bin_value,
        }
        params = {k: v for k, v in params.items() if v}

        return XGBClassifier(
            n_estimators=200,  # More trees than RF (shallow trees)
            max_depth=3,  # Shallow tree depth (prevents overfitting)
            learning_rate=0.05,  # Conservative learning rate
            subsample=0.8,  # 80% of samples per tree (bagging)
            colsample_bytree=0.8,  # 80% of features per tree
            colsample_bylevel=0.8,  # 80% of features per tree level
            min_child_weight=1,  # Minimum weight to split
            gamma=0,  # No regularization penalty
            reg_alpha=0.1,  # L1 regularization (light)
            reg_lambda=1.0,  # L2 regularization (standard)
            random_state=self.random_state,
            objective="multi:softmax",  # Multiclass classification
            num_class=3,  # 3 classes (Bearish, Neutral, Bullish)
            eval_metric="mlogloss",  # Evaluation metric
            verbosity=0,  # No training output
            n_jobs=n_jobs,  # Use all CPU cores (override via env)
            **params,
        )

    def train(
        self, features_df: pd.DataFrame, labels_series: pd.Series
    ) -> "GradientBoostingForecaster":
        """
        Train Gradient Boosting model on historical data.

        Args:
            features_df: DataFrame with technical indicators
                (shape: [N, num_features])
            labels_series: Series with directional labels {-1, 0, 1}
                (shape: [N])

        Returns:
            self (for method chaining)

        Raises:
            ValueError: If features or labels are invalid
        """
        # Validation
        if features_df.shape[0] != labels_series.shape[0]:
            raise ValueError(
                "Feature/label mismatch: " f"{features_df.shape[0]} vs {labels_series.shape[0]}"
            )

        if features_df.shape[0] < 100:
            raise ValueError(
                "Insufficient training data: " f"{features_df.shape[0]} rows (need >= 100)"
            )

        # Remove rows with NaN in features
        feature_mask = ~features_df.isna().any(axis=1)
        features_clean = features_df[feature_mask]
        labels_clean = labels_series[feature_mask]

        # Convert external labels (-1, 0, 1) to internal (0, 1, 2) for XGBoost
        # Handle both numeric and string labels
        if labels_clean.dtype == object:
            # String labels
            string_to_internal = {
                "bearish": 0,
                "neutral": 1,
                "bullish": 2,
                "Bearish": 0,
                "Neutral": 1,
                "Bullish": 2,
            }
            labels_internal = labels_clean.map(string_to_internal)
        else:
            # Numeric labels (-1, 0, 1)
            labels_internal = labels_clean.map(self.EXTERNAL_TO_INTERNAL)

        # Remove any rows where label mapping failed (NaN)
        valid_mask = ~labels_internal.isna()
        features_clean = features_clean[valid_mask]
        labels_internal = labels_internal[valid_mask].astype(int)

        logger.info(
            "Training GB Forecaster (%s): %s samples",
            self.horizon,
            len(features_clean),
        )

        # Check if we still have enough samples after filtering
        if len(features_clean) < 50:
            raise ValueError(
                "Insufficient training data after NaN filtering: "
                f"{len(features_clean)} rows (need >= 50)"
            )

        # Store feature names
        self.feature_names = features_df.columns.tolist()

        # Build and train model
        self.model = self._build_model()
        self.model.fit(X=features_clean, y=labels_internal)

        # Store training stats
        # Feature importance (may be gain-based depending on booster)
        importance_pairs: list[tuple[str, float]] = []
        try:
            importances = self.model.feature_importances_
            importance_pairs = sorted(
                zip(self.feature_names, importances),
                key=lambda kv: kv[1],
                reverse=True,
            )
        except Exception:  # noqa: BLE001
            # Fallback to booster scores if available
            try:
                booster = self.model.get_booster()
                score_dict = booster.get_score(importance_type="gain")
                importance_pairs = sorted(
                    score_dict.items(),
                    key=lambda kv: kv[1],
                    reverse=True,
                )
            except Exception:  # noqa: BLE001
                importance_pairs = []

        top_features = importance_pairs[:10]

        self.training_stats = {
            "n_samples": len(features_clean),
            "n_features": features_clean.shape[1],
            "class_distribution": labels_internal.value_counts().to_dict(),
            "training_accuracy": self.model.score(features_clean, labels_internal),
            "top_features": top_features,
        }

        self.is_trained = True
        logger.info(
            "GB model trained. Accuracy: %.3f",
            self.training_stats["training_accuracy"],
        )
        if top_features:
            logger.info(
                "GB top features: %s",
                ", ".join(f"{name}={score:.3f}" for name, score in top_features),
            )

        return self

    def predict(self, features_df: pd.DataFrame) -> Dict:
        """
        Predict stock direction on new data.

        Args:
            features_df: DataFrame with technical indicators
                (1 row = current bar)

        Returns:
            Dict with keys:
            - 'label': Prediction ('Bullish', 'Neutral', 'Bearish')
            - 'confidence': Probability of predicted class (0-1)
            - 'probabilities': All class probabilities
            - 'raw_prediction': Raw numeric label (-1, 0, 1)

        Raises:
            RuntimeError: If model not trained
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Use last row if DataFrame
        if isinstance(features_df, pd.DataFrame):
            features = features_df.iloc[-1:].values
        else:
            features = features_df

        # Predict (returns internal labels 0, 1, 2)
        prediction_internal = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]

        # Map internal to external label
        prediction_external = self.INTERNAL_TO_EXTERNAL[int(prediction_internal)]
        label = self.LABEL_MAP[prediction_external]
        confidence = float(np.max(probabilities))

        proba_dict = {
            "bearish": float(probabilities[0]),
            "neutral": float(probabilities[1]),
            "bullish": float(probabilities[2]),
        }

        return {
            "label": label,
            "confidence": confidence,
            "probabilities": proba_dict,
            "raw_prediction": prediction_external,
        }

    def predict_batch(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict for multiple rows (batch prediction).

        Args:
            features_df: DataFrame with technical indicators (multiple rows)

        Returns:
            DataFrame with predictions for each row
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        predictions_internal = self.model.predict(features_df)
        probabilities = self.model.predict_proba(features_df)

        # Convert internal predictions to external labels
        predictions_external = [
            self.INTERNAL_TO_EXTERNAL[int(pred)] for pred in predictions_internal
        ]

        result_df = pd.DataFrame(
            {
                "prediction": [self.LABEL_MAP[p] for p in predictions_external],
                "confidence": np.max(probabilities, axis=1),
                "prob_bearish": probabilities[:, 0],
                "prob_neutral": probabilities[:, 1],
                "prob_bullish": probabilities[:, 2],
            }
        )

        return result_df

    def feature_importance(self, top_n: int = 10) -> pd.DataFrame:
        """
        Get top N most important features.

        Args:
            top_n: Number of top features to return

        Returns:
            DataFrame with feature names and importance scores
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained.")

        importances = self.model.feature_importances_
        feature_importance_df = pd.DataFrame(
            {"feature": self.feature_names, "importance": importances}
        ).sort_values("importance", ascending=False)

        return feature_importance_df.head(top_n)

    def save(self, filepath: str) -> None:
        """Save trained model to disk."""
        with open(filepath, "wb") as f:
            pickle.dump(
                {"model": self.model, "feature_names": self.feature_names},
                f,
            )
        logger.info(f"Model saved to {filepath}")

    def load(self, filepath: str) -> "GradientBoostingForecaster":
        """Load trained model from disk."""
        with open(filepath, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.feature_names = data["feature_names"]
            self.is_trained = True
        logger.info(f"Model loaded from {filepath}")
        return self


if __name__ == "__main__":
    print("GradientBoostingForecaster imported successfully")
