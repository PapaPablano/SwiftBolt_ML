"""Model training for ensemble components.

Trains individual ML models (Random Forest, Gradient Boosting) with proper validation.
"""

import logging
from typing import Dict, List

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Train individual models with consistent interface."""
    
    def __init__(self, symbol: str, timeframe: str):
        """
        Initialize trainer.
        
        Args:
            symbol: Ticker (e.g., "AAPL")
            timeframe: Timeframe ID (e.g., "d1")
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.models = {}
        self.performances = {}
    
    def train_random_forest(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """
        Train Random Forest classifier.
        
        Args:
            train_features: Training feature matrix
            train_labels: Training labels
            valid_features: Validation feature matrix
            valid_labels: Validation labels
        
        Returns:
            Performance metrics dictionary
        """
        
        logger.info(f"Training Random Forest ({self.symbol}/{self.timeframe})")
        
        # Hyperparameters optimized for financial data
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        
        # Train
        rf.fit(train_features, train_labels)
        
        # Evaluate
        train_pred = rf.predict(train_features)
        valid_pred = rf.predict(valid_features)
        
        train_acc = accuracy_score(train_labels, train_pred)
        valid_acc = accuracy_score(valid_labels, valid_pred)
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            valid_labels, valid_pred, average="weighted", zero_division=0
        )
        
        perf = {
            "train_accuracy": float(train_acc),
            "valid_accuracy": float(valid_acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "n_features": len(train_features.columns),
            "n_samples_train": len(train_features),
            "n_samples_valid": len(valid_features),
        }
        
        self.models["rf"] = rf
        self.performances["rf"] = perf
        
        logger.info(f"  Train Acc: {train_acc:.1%}")
        logger.info(f"  Valid Acc: {valid_acc:.1%}")
        logger.info(f"  Overfit Margin: {(train_acc - valid_acc):.1%}")
        
        return perf
    
    def train_gradient_boosting(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """
        Train Gradient Boosting classifier.
        
        Args:
            train_features: Training feature matrix
            train_labels: Training labels
            valid_features: Validation feature matrix
            valid_labels: Validation labels
        
        Returns:
            Performance metrics dictionary
        """
        
        logger.info(f"Training Gradient Boosting ({self.symbol}/{self.timeframe})")
        
        gb = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=7,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        )
        
        # Train
        gb.fit(train_features, train_labels)
        
        # Evaluate
        train_pred = gb.predict(train_features)
        valid_pred = gb.predict(valid_features)
        
        train_acc = accuracy_score(train_labels, train_pred)
        valid_acc = accuracy_score(valid_labels, valid_pred)
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            valid_labels, valid_pred, average="weighted", zero_division=0
        )
        
        perf = {
            "train_accuracy": float(train_acc),
            "valid_accuracy": float(valid_acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "n_features": len(train_features.columns),
            "n_samples_train": len(train_features),
            "n_samples_valid": len(valid_features),
        }
        
        self.models["gb"] = gb
        self.performances["gb"] = perf
        
        logger.info(f"  Train Acc: {train_acc:.1%}")
        logger.info(f"  Valid Acc: {valid_acc:.1%}")
        logger.info(f"  Overfit Margin: {(train_acc - valid_acc):.1%}")
        
        return perf
    
    def train_all_models(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """
        Train all ensemble components.
        
        Args:
            train_features: Training feature matrix
            train_labels: Training labels
            valid_features: Validation feature matrix
            valid_labels: Validation labels
        
        Returns:
            Dictionary of performance metrics by model name
        """
        
        results = {}
        
        # Core models
        results["rf"] = self.train_random_forest(
            train_features, train_labels, valid_features, valid_labels
        )
        results["gb"] = self.train_gradient_boosting(
            train_features, train_labels, valid_features, valid_labels
        )
        
        # TODO: Add ARIMA-GARCH, Prophet, LSTM if needed
        # These are optional and slower to train
        
        return results
    
    def get_model_predictions(self, features: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Get predictions from all trained models.
        
        Args:
            features: Feature matrix to predict on
        
        Returns:
            Dictionary mapping model name to list of predictions
            Example: {"rf": ["BULLISH", "BEARISH", ...], "gb": [...]}
        """
        
        predictions = {}
        
        for model_name, model in self.models.items():
            try:
                preds = model.predict(features).tolist()
                predictions[model_name] = preds
            except Exception as e:
                logger.error(f"Prediction failed for {model_name}: {e}")
                # Return NEUTRAL as fallback
                predictions[model_name] = ["NEUTRAL"] * len(features)
        
        return predictions
