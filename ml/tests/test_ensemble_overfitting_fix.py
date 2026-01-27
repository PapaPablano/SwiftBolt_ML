"""Unit tests for ensemble overfitting fix (Phase 1).

Tests the new 2-model and 3-model ensemble configurations based on
research recommendations from ml_pipleline_refinement.md.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock settings before importing the module
mock_settings = MagicMock()
sys.modules["config.settings"] = MagicMock()
sys.modules["config.settings"].settings = mock_settings

# Import after mocking
from src.models.enhanced_ensemble_integration import (
    _bool_env,
    get_production_ensemble,
)
from src.models.multi_model_ensemble import MultiModelEnsemble


class TestBoolEnvHelper:
    """Test the _bool_env helper function."""

    def test_bool_env_true_values(self):
        """Test that _bool_env recognizes true values."""
        true_values = ["1", "true", "True", "TRUE", "yes", "Yes", "y", "Y", "on", "ON"]
        for val in true_values:
            with patch.dict(os.environ, {"TEST_VAR": val}):
                assert _bool_env("TEST_VAR") is True

    def test_bool_env_false_values(self):
        """Test that _bool_env recognizes false values."""
        false_values = ["0", "false", "False", "FALSE", "no", "n", "off", ""]
        for val in false_values:
            with patch.dict(os.environ, {"TEST_VAR": val}, clear=False):
                assert _bool_env("TEST_VAR") is False

    def test_bool_env_missing_uses_default(self):
        """Test that missing env var uses default."""
        with patch.dict(os.environ, {}, clear=True):
            assert _bool_env("NONEXISTENT", default=True) is True
            assert _bool_env("NONEXISTENT", default=False) is False


class TestTwoModelEnsemble:
    """Test 2-model ensemble (LSTM + ARIMA-GARCH)."""

    def test_2_model_ensemble_creation(self):
        """Test creation of 2-model ensemble."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "false",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify ensemble is correctly configured
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is False
            assert ensemble.enable_rf is False
            assert ensemble.enable_transformer is False
            assert ensemble.enable_prophet is False
            # Verify 2 models are enabled
            assert ensemble.n_models == 2

    def test_2_model_ensemble_has_lstm_arima(self):
        """Test that 2-model ensemble includes LSTM and ARIMA-GARCH."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify correct models are enabled
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is False
            assert ensemble.enable_rf is False


class TestThreeModelEnsemble:
    """Test 3-model ensemble (LSTM + ARIMA-GARCH + XGBoost)."""

    def test_3_model_ensemble_creation(self):
        """Test creation of 3-model ensemble."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "3",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify ensemble is correctly configured with 3 models
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True
            assert ensemble.enable_rf is False
            assert ensemble.enable_transformer is False
            assert ensemble.enable_prophet is False
            assert ensemble.n_models == 3

    def test_3_model_ensemble_has_lstm_arima_gb(self):
        """Test that 3-model ensemble includes LSTM, ARIMA-GARCH, and XGBoost."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "3",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify correct models are enabled
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True
            assert ensemble.enable_rf is False

    def test_3_model_ensemble_disables_transformer(self):
        """Test that 3-model ensemble disables Transformer and Prophet."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "3",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify redundant models are disabled
            assert ensemble.enable_transformer is False
            assert ensemble.enable_prophet is False
            assert ensemble.enable_rf is False


class TestLegacyFourModelEnsemble:
    """Test backward compatibility with legacy 4-model ensemble."""

    def test_4_model_ensemble_creation(self):
        """Test creation of legacy 4-model ensemble (for backward compatibility)."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "4",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "true",
                "ENABLE_TRANSFORMER": "false",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify ensemble includes all 4 models
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True
            # Transformer should be disabled even if explicitly enabled for 4-model
            # because TensorFlow causes issues

    def test_4_model_ensemble_is_configured(self):
        """Test that legacy 4-model ensemble is configured correctly."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "4",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Should have 4 models (but Transformer disabled in workflow)
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True


class TestDefaultModelCount:
    """Test default ENSEMBLE_MODEL_COUNT behavior."""

    def test_default_model_count_is_2(self):
        """Test that default ENSEMBLE_MODEL_COUNT is 2."""
        # Clear the var to test default
        env = dict(os.environ)
        if "ENSEMBLE_MODEL_COUNT" in env:
            del env["ENSEMBLE_MODEL_COUNT"]

        with patch.dict(os.environ, env, clear=True):
            ensemble = get_production_ensemble(horizon="1D")

            # Should default to 2-model with LSTM and ARIMA only
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is False
            assert ensemble.n_models == 2

    def test_invalid_model_count_uses_default(self):
        """Test that invalid ENSEMBLE_MODEL_COUNT falls back to default."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "99",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Should fall back to 2-model default
            assert ensemble.enable_gb is False
            assert ensemble.n_models == 2


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides."""

    def test_override_lstm_enable(self):
        """Test overriding ENABLE_LSTM."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "false",
                "ENABLE_ARIMA_GARCH": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")
            assert ensemble.enable_lstm is False

    def test_override_arima_enable(self):
        """Test overriding ENABLE_ARIMA_GARCH."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "false",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")
            assert ensemble.enable_arima_garch is False

    def test_override_gb_enable_for_3_model(self):
        """Test enabling XGBoost for 3-model ensemble."""
        with patch.dict(
            os.environ,
            {
                "ENSEMBLE_MODEL_COUNT": "3",
                "ENABLE_GB": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")
            assert ensemble.enable_gb is True


class TestMultiModelEnsembleWeights:
    """Test MultiModelEnsemble weight calculation."""

    def test_2_model_weight_calculation(self):
        """Test weight calculation for 2-model ensemble."""
        ensemble = MultiModelEnsemble(
            horizon="1D",
            enable_rf=False,
            enable_gb=False,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=True,
            enable_transformer=False,
        )

        weights = ensemble._calculate_default_weights()

        # Should return 50/50 split
        assert len(weights) == 2
        assert weights[ensemble.MODEL_LSTM] == 0.50
        assert weights[ensemble.MODEL_AG] == 0.50
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_3_model_weight_calculation(self):
        """Test weight calculation for 3-model ensemble."""
        ensemble = MultiModelEnsemble(
            horizon="1D",
            enable_rf=False,
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=True,
            enable_transformer=False,
        )

        weights = ensemble._calculate_default_weights()

        # Should return 30/40/30 split
        assert len(weights) == 3
        assert weights[ensemble.MODEL_AG] == 0.30
        assert weights[ensemble.MODEL_LSTM] == 0.40
        assert weights[ensemble.MODEL_GB] == 0.30
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_legacy_4_model_weight_calculation(self):
        """Test weight calculation for legacy 4-model ensemble."""
        ensemble = MultiModelEnsemble(
            horizon="1D",
            enable_rf=False,
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=True,
            enable_transformer=True,
        )

        weights = ensemble._calculate_default_weights()

        # Should return legacy 4-model weights
        assert len(weights) == 4
        assert weights[ensemble.MODEL_AG] == 0.20
        assert weights[ensemble.MODEL_GB] == 0.35
        assert weights[ensemble.MODEL_LSTM] == 0.25
        assert weights[ensemble.MODEL_TRANSFORMER] == 0.20
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_fallback_equal_weights(self):
        """Test fallback to equal weights for unsupported configuration."""
        ensemble = MultiModelEnsemble(
            horizon="1D",
            enable_rf=True,  # Unusual combination
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=False,
            enable_transformer=False,
        )

        weights = ensemble._calculate_default_weights()

        # Should return equal weights for unsupported config
        expected_weight = 1.0 / 3
        for model in [ensemble.MODEL_RF, ensemble.MODEL_GB, ensemble.MODEL_AG]:
            assert abs(weights[model] - expected_weight) < 1e-6
        assert abs(sum(weights.values()) - 1.0) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
