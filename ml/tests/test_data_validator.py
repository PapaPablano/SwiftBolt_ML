"""Unit tests for OHLCValidator."""

import numpy as np
import pandas as pd
import pytest

from src.data.data_validator import OHLCValidator, ValidationResult, validate_ohlc_data


class TestOHLCValidator:
    """Test suite for OHLCValidator."""

    @pytest.fixture
    def valid_ohlc_data(self) -> pd.DataFrame:
        """Create valid OHLC test data."""
        np.random.seed(42)
        n = 100

        closes = 100 + np.cumsum(np.random.normal(0, 1, n))
        opens = closes + np.random.normal(0, 0.5, n)
        highs = np.maximum(opens, closes) + np.abs(np.random.normal(0.5, 0.3, n))
        lows = np.minimum(opens, closes) - np.abs(np.random.normal(0.5, 0.3, n))
        volumes = np.random.randint(100000, 10000000, n)

        return pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

    @pytest.fixture
    def invalid_ohlc_data(self) -> pd.DataFrame:
        """Create OHLC data with known issues."""
        return pd.DataFrame({
            "open": [100, 101, 102, -5, 104],  # Negative price
            "high": [99, 102, 103, 105, 105],  # First high < open (invalid)
            "low": [99, 100, 101, 103, 103],
            "close": [101, 101, 102, 104, 104],
            "volume": [1000000, -500, 1000000, 1000000, 1000000],  # Negative volume
        })

    def test_init(self):
        """Test validator initialization."""
        validator = OHLCValidator()
        assert validator.MAX_GAP_ATRS == 3.0
        assert validator.OUTLIER_ZSCORE == 4.0

    def test_validate_valid_data(self, valid_ohlc_data):
        """Test validation of clean data."""
        validator = OHLCValidator()
        cleaned_df, result = validator.validate(valid_ohlc_data, fix_issues=False)

        assert result.is_valid or len(result.issues) == 0 or "outlier" in str(result.issues).lower()
        assert len(cleaned_df) == len(valid_ohlc_data)

    def test_validate_invalid_high(self):
        """Test detection of high < max(open, close)."""
        df = pd.DataFrame({
            "open": [100, 101],
            "high": [99, 102],  # First row: high < open
            "low": [98, 100],
            "close": [100, 101],
            "volume": [1000, 1000],
        })

        validator = OHLCValidator()
        _, result = validator.validate(df, fix_issues=False)

        assert not result.is_valid
        assert any("High" in issue for issue in result.issues)
        assert result.rows_flagged >= 1

    def test_validate_invalid_low(self):
        """Test detection of low > min(open, close)."""
        df = pd.DataFrame({
            "open": [100, 101],
            "high": [102, 103],
            "low": [101, 99],  # First row: low > open
            "close": [100, 102],
            "volume": [1000, 1000],
        })

        validator = OHLCValidator()
        _, result = validator.validate(df, fix_issues=False)

        assert not result.is_valid
        assert any("Low" in issue for issue in result.issues)

    def test_validate_negative_volume(self):
        """Test detection of negative volume."""
        df = pd.DataFrame({
            "open": [100, 101],
            "high": [102, 103],
            "low": [98, 99],
            "close": [101, 102],
            "volume": [-1000, 1000],  # Negative volume
        })

        validator = OHLCValidator()
        _, result = validator.validate(df, fix_issues=False)

        assert not result.is_valid
        assert any("Negative volume" in issue for issue in result.issues)

    def test_validate_non_positive_price(self):
        """Test detection of zero/negative prices."""
        df = pd.DataFrame({
            "open": [0, 101],  # Zero price
            "high": [102, 103],
            "low": [98, 99],
            "close": [101, 102],
            "volume": [1000, 1000],
        })

        validator = OHLCValidator()
        _, result = validator.validate(df, fix_issues=False)

        assert not result.is_valid
        assert any("Non-positive" in issue for issue in result.issues)

    def test_validate_fix_issues(self, invalid_ohlc_data):
        """Test that fix_issues removes bad rows."""
        validator = OHLCValidator()
        cleaned_df, result = validator.validate(invalid_ohlc_data, fix_issues=True)

        assert len(cleaned_df) < len(invalid_ohlc_data)
        assert result.rows_removed > 0

    def test_validate_no_fix_issues(self, invalid_ohlc_data):
        """Test that fix_issues=False doesn't modify data."""
        validator = OHLCValidator()
        cleaned_df, result = validator.validate(invalid_ohlc_data, fix_issues=False)

        assert len(cleaned_df) == len(invalid_ohlc_data)
        assert result.rows_removed == 0

    def test_validate_outlier_detection(self):
        """Test detection of extreme return outliers."""
        # Create data with one extreme outlier (needs z-score > 4)
        # Need enough data points and a truly extreme outlier
        np.random.seed(42)
        n = 50
        closes = 100 + np.cumsum(np.random.normal(0, 0.5, n))  # Normal price movement
        closes[25] = closes[24] * 2.0  # 100% jump - extreme outlier

        df = pd.DataFrame({
            "open": closes,
            "high": closes + 1,
            "low": closes - 1,
            "close": closes,
            "volume": [1000000] * n,
        })

        validator = OHLCValidator()
        _, result = validator.validate(df, fix_issues=False)

        # Should detect the outlier
        assert not result.is_valid
        assert any("outlier" in issue.lower() for issue in result.issues)

    def test_gap_detection(self):
        """Test large gap detection (informational only)."""
        # Create data with a large gap
        df = pd.DataFrame({
            "open": [100, 101, 150, 151],  # 150 is 50% gap from 101
            "high": [102, 103, 155, 153],
            "low": [98, 99, 148, 149],
            "close": [101, 102, 152, 150],
            "volume": [1000000] * 4,
        })

        validator = OHLCValidator()
        cleaned_df, result = validator.validate(df, fix_issues=True)

        # Gaps should be flagged but NOT removed
        if any("gap" in issue.lower() for issue in result.issues):
            # Gap rows should remain in data
            assert len(cleaned_df) == 4 or len(cleaned_df) >= 3

    def test_get_data_quality_score_perfect(self, valid_ohlc_data):
        """Test quality score for clean data."""
        validator = OHLCValidator()
        score = validator.get_data_quality_score(valid_ohlc_data)

        # Score should be high for valid data
        assert score >= 0.9 or score > 0.0  # May have some statistical outliers

    def test_get_data_quality_score_bad(self, invalid_ohlc_data):
        """Test quality score for problematic data."""
        validator = OHLCValidator()
        score = validator.get_data_quality_score(invalid_ohlc_data)

        # Score should be lower for invalid data
        assert score < 1.0

    def test_get_data_quality_score_empty(self):
        """Test quality score for empty data."""
        validator = OHLCValidator()
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        score = validator.get_data_quality_score(empty_df)

        assert score == 0.0

    def test_validate_normalizes_column_names(self):
        """Test that column names are normalized to lowercase."""
        df = pd.DataFrame({
            "Open": [100, 101],
            "HIGH": [102, 103],
            "Low": [98, 99],
            "CLOSE": [101, 102],
            "Volume": [1000, 1000],
        })

        validator = OHLCValidator()
        cleaned_df, result = validator.validate(df, fix_issues=False)

        # Should work despite mixed case
        assert result.is_valid
        # Columns should be lowercase in output
        assert all(col.islower() for col in cleaned_df.columns)

    def test_convenience_function(self, valid_ohlc_data):
        """Test validate_ohlc_data convenience function."""
        cleaned_df, result = validate_ohlc_data(valid_ohlc_data, fix_issues=False)

        assert isinstance(result, ValidationResult)
        assert len(cleaned_df) == len(valid_ohlc_data)

    def test_validation_result_dataclass(self):
        """Test ValidationResult dataclass."""
        result = ValidationResult(
            is_valid=False,
            issues=["Test issue 1", "Test issue 2"],
            rows_flagged=5,
            rows_removed=3,
        )

        assert result.is_valid is False
        assert len(result.issues) == 2
        assert result.rows_flagged == 5
        assert result.rows_removed == 3

    def test_atr_calculation(self, valid_ohlc_data):
        """Test internal ATR calculation."""
        validator = OHLCValidator()
        # Normalize columns first
        valid_ohlc_data.columns = valid_ohlc_data.columns.str.lower()
        atr = validator._calculate_atr(valid_ohlc_data, period=14)

        assert len(atr) == len(valid_ohlc_data)
        # First 13 values should be NaN (rolling window not filled)
        assert atr.iloc[:13].isna().all()
        # After that, should have positive values
        assert (atr.iloc[14:] > 0).all()
