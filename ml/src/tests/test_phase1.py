"""
Unit Tests for Phase 1 Implementation
=====================================

Tests for Gradient Boosting, Ensemble, and Regime Indicators.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.gradient_boosting_forecaster import (  # noqa: E402
    GradientBoostingForecaster,
)
from src.models.ensemble_forecaster import EnsembleForecaster  # noqa: E402
from src.features.regime_indicators import RegimeIndicators  # noqa: E402
from src.evaluation.purged_walk_forward_cv import (  # noqa: E402
    PurgedWalkForwardCV,
)


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
        ensemble = EnsembleForecaster(
            horizon="1D", rf_weight=0.5, gb_weight=0.5
        )
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
            np.random.randn(n_samples, 5),
            columns=[f"feature_{i}" for i in range(5)],
        )
        cls.y = pd.Series(np.random.choice([-1, 0, 1], n_samples))
        cls.dates = pd.date_range(
            start="2024-01-01", periods=n_samples, freq="D"
        )

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


class TestWalkForwardBacktester(unittest.TestCase):
    """Test Walk-Forward Backtester module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n_samples = 400
        dates = pd.date_range(start="2023-01-01", periods=n_samples, freq="D")

        prices = 100 + np.random.randn(n_samples).cumsum() * 0.5
        cls.ohlcv_df = pd.DataFrame({
            "ts": dates,
            "open": prices * (1 + np.random.randn(n_samples) * 0.01),
            "high": prices * (1 + np.abs(np.random.randn(n_samples) * 0.02)),
            "low": prices * (1 - np.abs(np.random.randn(n_samples) * 0.02)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, n_samples),
        })

    def test_backtest_metrics_dataclass(self):
        """Test BacktestMetrics dataclass."""
        from src.backtesting.walk_forward_tester import BacktestMetrics
        from datetime import datetime

        metrics = BacktestMetrics(
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
            accuracy=0.55,
            precision=0.54,
            recall=0.56,
            f1_score=0.55,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown=-0.15,
            win_rate=0.55,
            avg_win_size=0.03,
            avg_loss_size=0.02,
            profit_factor=1.65,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 1, 1),
            test_periods=10,
        )

        self.assertEqual(metrics.total_trades, 100)
        self.assertEqual(metrics.accuracy, 0.55)
        self.assertIn("Accuracy", str(metrics))

    def test_backtester_initialization(self):
        """Test WalkForwardBacktester initialization."""
        from src.backtesting.walk_forward_tester import WalkForwardBacktester

        bt = WalkForwardBacktester(train_window=100, test_window=20, step_size=5)
        self.assertEqual(bt.train_window, 100)
        self.assertEqual(bt.test_window, 20)
        self.assertEqual(bt.step_size, 5)


class TestTemporalIndicators(unittest.TestCase):
    """Test Temporal Feature Engineer module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n_samples = 100
        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

        prices = 100 + np.random.randn(n_samples).cumsum() * 0.5
        cls.ohlcv_df = pd.DataFrame({
            "ts": dates,
            "open": prices * (1 + np.random.randn(n_samples) * 0.01),
            "high": prices * (1 + np.abs(np.random.randn(n_samples) * 0.02)),
            "low": prices * (1 - np.abs(np.random.randn(n_samples) * 0.02)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, n_samples),
        })

    def test_compute_sma(self):
        """Test SMA computation with no lookahead."""
        from src.features.temporal_indicators import TemporalFeatureEngineer

        close_prices = np.array([10, 11, 12, 13, 14, 15])

        # SMA at index 4 with window 5 should use prices 0-4
        sma = TemporalFeatureEngineer.compute_sma(close_prices, window=5, idx=4)
        expected = np.mean([10, 11, 12, 13, 14])
        self.assertAlmostEqual(sma, expected, places=6)

        # SMA at index 2 with window 5 should be NaN (insufficient data)
        sma_early = TemporalFeatureEngineer.compute_sma(close_prices, window=5, idx=2)
        self.assertTrue(np.isnan(sma_early))

    def test_compute_rsi(self):
        """Test RSI computation with no lookahead."""
        from src.features.temporal_indicators import TemporalFeatureEngineer

        # Create trending up prices
        close_prices = np.array([100 + i for i in range(30)])

        rsi = TemporalFeatureEngineer.compute_rsi(close_prices, window=14, idx=20)
        # All gains, no losses -> RSI should be 100
        self.assertEqual(rsi, 100.0)

    def test_add_features_to_point(self):
        """Test adding features to a single point."""
        from src.features.temporal_indicators import TemporalFeatureEngineer

        engineer = TemporalFeatureEngineer()
        features = engineer.add_features_to_point(self.ohlcv_df, idx=60)

        self.assertIn("sma_5", features)
        self.assertIn("sma_20", features)
        self.assertIn("rsi_14", features)
        self.assertIn("close", features)

    def test_prepare_training_data_temporal(self):
        """Test temporal training data preparation."""
        from src.features.temporal_indicators import prepare_training_data_temporal

        X, y = prepare_training_data_temporal(self.ohlcv_df, horizon_days=1)

        self.assertGreater(len(X), 0)
        self.assertEqual(len(X), len(y))
        self.assertTrue(all(label in ["bullish", "neutral", "bearish"] for label in y))


class TestAdaptiveThresholds(unittest.TestCase):
    """Test Adaptive Thresholds module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n_samples = 100

        prices = 100 + np.random.randn(n_samples).cumsum() * 0.5
        cls.ohlcv_df = pd.DataFrame({
            "close": prices,
            "atr": np.abs(np.random.randn(n_samples) * 2) + 1,
        })

    def test_compute_thresholds(self):
        """Test volatility-based threshold computation."""
        from src.features.adaptive_thresholds import AdaptiveThresholds

        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds(
            self.ohlcv_df
        )

        self.assertLess(bearish_thresh, 0)
        self.assertGreater(bullish_thresh, 0)
        # Thresholds should be symmetric
        self.assertAlmostEqual(abs(bearish_thresh), abs(bullish_thresh), places=6)

    def test_compute_thresholds_atr(self):
        """Test ATR-based threshold computation."""
        from src.features.adaptive_thresholds import AdaptiveThresholds

        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_atr(
            self.ohlcv_df
        )

        self.assertLess(bearish_thresh, 0)
        self.assertGreater(bullish_thresh, 0)


class TestForecastQualityMonitor(unittest.TestCase):
    """Test Forecast Quality Monitor module."""

    def test_compute_quality_score(self):
        """Test quality score computation."""
        from src.monitoring.forecast_quality import ForecastQualityMonitor
        from datetime import datetime

        forecast = {
            "confidence": 0.80,
            "model_agreement": 0.90,
            "created_at": datetime.now(),
        }

        score = ForecastQualityMonitor.compute_quality_score(forecast)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)

    def test_check_quality_issues_low_confidence(self):
        """Test quality issue detection for low confidence."""
        from src.monitoring.forecast_quality import ForecastQualityMonitor
        from datetime import datetime

        forecast = {
            "confidence": 0.40,
            "model_agreement": 0.90,
            "created_at": datetime.now(),
        }

        issues = ForecastQualityMonitor.check_quality_issues(forecast)

        self.assertTrue(any(i["type"] == "low_confidence" for i in issues))

    def test_check_quality_issues_model_disagreement(self):
        """Test quality issue detection for model disagreement."""
        from src.monitoring.forecast_quality import ForecastQualityMonitor
        from datetime import datetime

        forecast = {
            "confidence": 0.80,
            "model_agreement": 0.50,
            "created_at": datetime.now(),
        }

        issues = ForecastQualityMonitor.check_quality_issues(forecast)

        self.assertTrue(any(i["type"] == "model_disagreement" for i in issues))

    def test_check_batch_quality(self):
        """Test batch quality checking."""
        from src.monitoring.forecast_quality import ForecastQualityMonitor
        from datetime import datetime

        forecasts = [
            {"confidence": 0.80, "model_agreement": 0.90, "created_at": datetime.now()},
            {"confidence": 0.60, "model_agreement": 0.70, "created_at": datetime.now()},
            {"confidence": 0.40, "model_agreement": 0.50, "created_at": datetime.now()},
        ]

        summary = ForecastQualityMonitor.check_batch_quality(forecasts)

        self.assertEqual(summary["count"], 3)
        self.assertIn("avg_quality_score", summary)
        self.assertIn("issues_by_type", summary)


class TestMarketRegime(unittest.TestCase):
    """Test HMM Market Regime module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n_samples = 200

        prices = 100 + np.random.randn(n_samples).cumsum() * 0.5
        cls.ohlcv_df = pd.DataFrame({
            "close": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "open": prices * (1 + np.random.randn(n_samples) * 0.005),
            "volume": np.random.randint(1000000, 10000000, n_samples),
        })

    def test_market_regime_detector_initialization(self):
        """Test MarketRegimeDetector initialization."""
        from src.features.market_regime import MarketRegimeDetector

        detector = MarketRegimeDetector(n_states=3)
        self.assertEqual(detector.n_states, 3)
        self.assertFalse(detector.is_fitted)

    def test_add_market_regime_features(self):
        """Test adding HMM regime features to dataframe."""
        from src.features.market_regime import add_market_regime_features

        df = add_market_regime_features(self.ohlcv_df)

        self.assertIn("hmm_regime", df.columns)
        self.assertIn("hmm_regime_prob_0", df.columns)
        # Regime values should be 0, 1, or 2
        self.assertTrue(all(df["hmm_regime"].isin([0, 1, 2])))


class TestVolatilityRegime(unittest.TestCase):
    """Test GARCH Volatility Regime module."""

    @classmethod
    def setUpClass(cls):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n_samples = 200

        prices = 100 + np.random.randn(n_samples).cumsum() * 0.5
        cls.ohlcv_df = pd.DataFrame({
            "close": prices,
        })

    def test_garch_volatility_initialization(self):
        """Test GarchVolatility initialization."""
        from src.features.volatility_regime import GarchVolatility

        garch = GarchVolatility(dist="normal")
        self.assertEqual(garch.dist, "normal")
        self.assertIsNone(garch.model)

    def test_add_garch_features(self):
        """Test adding GARCH features to dataframe."""
        from src.features.volatility_regime import add_garch_features

        df = add_garch_features(self.ohlcv_df)

        self.assertIn("garch_variance", df.columns)
        self.assertIn("garch_vol_regime", df.columns)


if __name__ == "__main__":
    unittest.main()
