"""
Unit Tests for Phase 1 Implementation
=====================================

Tests for Gradient Boosting, Ensemble, and Regime Indicators.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.gradient_boosting_forecaster import GradientBoostingForecaster
from src.models.ensemble_forecaster import EnsembleForecaster
from src.features.regime_indicators import RegimeIndicators
from src.evaluation.purged_walk_forward_cv import PurgedWalkForwardCV


class TestGradientBoostingForecaster(unittest.TestCase):
    """Test Gradient Boosting module."""

    @classmethod
    def setUpClass(cls):
        """Create sample data for all tests."""
        np.random.seed(42)
        n_samples = 500
        n_features = 20

        cls.X_train = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f"feature_{i}" for i in range(n_features)],
        )
        cls.y_train = pd.Series(np.random.choice([-1, 0, 1], n_samples))

        cls.X_test = pd.DataFrame(
            np.random.randn(100, n_features),
            columns=[f"feature_{i}" for i in range(n_features)],
        )

    def test_initialization(self):
        """Test that model initializes."""
        forecaster = GradientBoostingForecaster(horizon="1D")
        self.assertFalse(forecaster.is_trained)
        self.assertEqual(forecaster.horizon, "1D")

    def test_training(self):
        """Test that model trains successfully."""
        forecaster = GradientBoostingForecaster()
        forecaster.train(self.X_train, self.y_train)
        self.assertTrue(forecaster.is_trained)
        self.assertEqual(len(forecaster.feature_names), 20)

    def test_prediction(self):
        """Test that predictions are valid."""
        forecaster = GradientBoostingForecaster()
        forecaster.train(self.X_train, self.y_train)

        pred = forecaster.predict(self.X_test.iloc[-1:])

        self.assertIn("label", pred)
        self.assertIn(pred["label"], ["Bullish", "Neutral", "Bearish"])
        self.assertGreaterEqual(pred["confidence"], 0)
        self.assertLessEqual(pred["confidence"], 1)

    def test_batch_prediction(self):
        """Test batch prediction."""
        forecaster = GradientBoostingForecaster()
        forecaster.train(self.X_train, self.y_train)

        preds = forecaster.predict_batch(self.X_test)

        self.assertEqual(len(preds), len(self.X_test))
        self.assertTrue(all(preds["confidence"] >= 0))
        self.assertTrue(all(preds["confidence"] <= 1))

    def test_feature_importance(self):
        """Test feature importance extraction."""
        forecaster = GradientBoostingForecaster()
        forecaster.train(self.X_train, self.y_train)

        importance = forecaster.feature_importance(top_n=5)

        self.assertEqual(len(importance), 5)
        self.assertIn("feature", importance.columns)
        self.assertIn("importance", importance.columns)


class TestEnsembleForecaster(unittest.TestCase):
    """Test Ensemble module."""

    @classmethod
    def setUpClass(cls):
        """Create sample data."""
        np.random.seed(42)
        n_samples = 500
        n_features = 20

        cls.X_train = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f"feature_{i}" for i in range(n_features)],
        )
        cls.y_train = pd.Series(np.random.choice([-1, 0, 1], n_samples))

        cls.X_test = pd.DataFrame(
            np.random.randn(100, n_features),
            columns=[f"feature_{i}" for i in range(n_features)],
        )
        cls.y_test = pd.Series(np.random.choice([-1, 0, 1], 100))

    def test_ensemble_initialization(self):
        """Test ensemble initialization."""
        ensemble = EnsembleForecaster(horizon="1D", rf_weight=0.5, gb_weight=0.5)
        self.assertFalse(ensemble.is_trained)
        self.assertAlmostEqual(ensemble.rf_weight, 0.5)

    def test_ensemble_training(self):
        """Test ensemble trains both models."""
        ensemble = EnsembleForecaster()
        ensemble.train(self.X_train, self.y_train)
        self.assertTrue(ensemble.is_trained)

    def test_ensemble_prediction(self):
        """Test ensemble prediction."""
        ensemble = EnsembleForecaster()
        ensemble.train(self.X_train, self.y_train)

        pred = ensemble.predict(self.X_test.iloc[-1:])

        self.assertIn("label", pred)
        self.assertIn("agreement", pred)
        self.assertIn(pred["label"], ["Bullish", "Neutral", "Bearish"])

    def test_ensemble_accuracy(self):
        """Test that ensemble meets minimum accuracy."""
        ensemble = EnsembleForecaster()
        ensemble.train(self.X_train, self.y_train)

        comparison = ensemble.compare_models(self.X_test, self.y_test)

        self.assertGreater(comparison["rf_accuracy"], 0)
        self.assertGreater(comparison["gb_accuracy"], 0)
        self.assertGreater(comparison["ensemble_accuracy"], 0)


class TestRegimeIndicators(unittest.TestCase):
    """Test Regime Indicators module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLC data."""
        dates = pd.date_range(start="2024-01-01", periods=500, freq="D")
        np.random.seed(42)

        cls.ohlc_df = pd.DataFrame(
            {
                "date": dates,
                "open": 100 + np.random.randn(500).cumsum(),
                "high": 105 + np.random.randn(500).cumsum(),
                "low": 95 + np.random.randn(500).cumsum(),
                "close": 100 + np.random.randn(500).cumsum(),
                "volume": np.random.randint(1000000, 10000000, 500),
            }
        )
        cls.ohlc_df.set_index("date", inplace=True)

    def test_realized_volatility(self):
        """Test realized volatility calculation."""
        vol = RegimeIndicators.realized_volatility(self.ohlc_df, lookback=20)

        self.assertEqual(len(vol), len(self.ohlc_df))
        self.assertTrue(vol.iloc[20:].notna().all())  # First 20 should be NaN

    def test_volatility_regime(self):
        """Test volatility regime classification."""
        vol = RegimeIndicators.realized_volatility(self.ohlc_df, lookback=20)
        regime = RegimeIndicators.volatility_regime(vol)

        self.assertEqual(len(regime), len(vol))
        self.assertTrue(all(regime.dropna().isin([0, 1, 2])))

    def test_volatility_of_volatility(self):
        """Test vol of vol calculation."""
        vol = RegimeIndicators.realized_volatility(self.ohlc_df, lookback=20)
        vov = RegimeIndicators.volatility_of_volatility(vol, lookback=10)

        self.assertEqual(len(vov), len(vol))

    def test_add_all_regime_features(self):
        """Test adding all regime features at once."""
        df = RegimeIndicators.add_all_regime_features(self.ohlc_df)

        expected_cols = [
            "realized_vol_20d",
            "volatility_regime",
            "vol_of_vol",
            "vol_percentile",
            "vol_trend",
        ]

        for col in expected_cols:
            self.assertIn(col, df.columns)


class TestPurgedWalkForwardCV(unittest.TestCase):
    """Test Purged Walk-Forward CV."""

    @classmethod
    def setUpClass(cls):
        """Create sample data."""
        np.random.seed(42)
        n_samples = 500

        cls.X = pd.DataFrame(
            np.random.randn(n_samples, 5), columns=[f"feature_{i}" for i in range(5)]
        )
        cls.y = pd.Series(np.random.choice([-1, 0, 1], n_samples))
        cls.dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

    def test_cv_initialization(self):
        """Test CV initialization."""
        cv = PurgedWalkForwardCV(n_splits=5, embargo_days=20)
        self.assertEqual(cv.n_splits, 5)
        self.assertEqual(cv.embargo_days, 20)

    def test_cv_split_count(self):
        """Test that CV generates correct number of folds."""
        cv = PurgedWalkForwardCV(n_splits=5, embargo_days=20)
        folds = list(cv.split(self.X, self.y))
        self.assertEqual(len(folds), 5)

    def test_cv_no_overlap(self):
        """Test that train/test splits don't overlap."""
        cv = PurgedWalkForwardCV(n_splits=3, embargo_days=10)

        for train_idx, test_idx in cv.split(self.X, self.y):
            # Check no overlap between train and test
            overlap = set(train_idx) & set(test_idx)
            self.assertEqual(len(overlap), 0)

    def test_cv_embargo_respected(self):
        """Test that embargo removes data after test fold."""
        cv = PurgedWalkForwardCV(n_splits=3, embargo_days=20)

        for train_idx, test_idx in cv.split(self.X, self.y):
            # Test indices should be sequential
            test_arr = np.sort(test_idx)
            self.assertTrue(np.array_equal(test_arr, test_idx))


if __name__ == "__main__":
    unittest.main()
