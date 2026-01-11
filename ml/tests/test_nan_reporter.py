"""Tests for NaN Reporter utility."""

import pandas as pd
import pytest
import numpy as np

from src.features.nan_reporter import NaNReporter, ColumnReport, DataFrameReport


class TestNaNReporter:
    """Tests for NaNReporter class."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame with some NaN values."""
        return pd.DataFrame(
            {
                "a": [1.0, 2.0, np.nan, 4.0, 5.0],
                "b": [1.0, np.nan, np.nan, np.nan, 5.0],
                "c": [1.0, 2.0, 3.0, 4.0, 5.0],  # No NaNs
                "d": [np.nan, np.nan, np.nan, np.nan, np.nan],  # All NaNs
            }
        )

    @pytest.fixture
    def clean_df(self):
        """Create clean DataFrame with no NaN values."""
        return pd.DataFrame(
            {
                "x": [1.0, 2.0, 3.0],
                "y": [4.0, 5.0, 6.0],
            }
        )

    def test_scan_dataframe(self, sample_df):
        """Test basic DataFrame scanning."""
        reporter = NaNReporter()
        report = reporter.scan_dataframe(sample_df)

        assert report.total_rows == 5
        assert report.total_columns == 4
        assert report.total_nans == 9  # 1 + 3 + 0 + 5
        assert report.columns_with_nans == 3  # a, b, d

    def test_column_report_details(self, sample_df):
        """Test column-level report details."""
        reporter = NaNReporter()
        report = reporter.scan_dataframe(sample_df)

        # Column 'a' has 1 NaN
        assert report.column_reports["a"].nan_count == 1
        assert report.column_reports["a"].nan_percentage == 20.0

        # Column 'c' is clean
        assert report.column_reports["c"].nan_count == 0
        assert report.column_reports["c"].is_clean

        # Column 'd' is all NaNs
        assert report.column_reports["d"].nan_count == 5
        assert report.column_reports["d"].nan_percentage == 100.0

    def test_clean_dataframe(self, clean_df):
        """Test scanning a clean DataFrame."""
        reporter = NaNReporter()
        report = reporter.scan_dataframe(clean_df)

        assert report.is_clean
        assert report.total_nans == 0
        assert report.columns_with_nans == 0
        assert report.severity == "clean"

    def test_severity_levels(self, sample_df):
        """Test severity classification."""
        reporter = NaNReporter()
        report = reporter.scan_dataframe(sample_df)

        # Column 'a' has 20% NaNs -> high (>=20% is high)
        assert report.column_reports["a"].severity == "high"

        # Column 'c' has 0% NaNs -> clean
        assert report.column_reports["c"].severity == "clean"

        # Column 'd' has 100% NaNs -> high
        assert report.column_reports["d"].severity == "high"

    def test_get_report_string(self, sample_df):
        """Test report string generation."""
        reporter = NaNReporter()
        reporter.scan_dataframe(sample_df)
        report_str = reporter.get_report()

        assert "NaN REPORT" in report_str
        assert "Total NaNs: 9" in report_str
        assert "COLUMNS WITH NANS" in report_str

    def test_get_report_dataframe(self, sample_df):
        """Test report DataFrame generation."""
        reporter = NaNReporter()
        reporter.scan_dataframe(sample_df)
        report_df = reporter.get_report_dataframe()

        assert len(report_df) == 4
        assert "column" in report_df.columns
        assert "nan_count" in report_df.columns
        assert "severity" in report_df.columns

    def test_impute_ffill(self, sample_df):
        """Test forward fill imputation."""
        reporter = NaNReporter()
        df_clean = reporter.impute_missing(sample_df, method="ffill")

        # Column 'a' should have NaN filled
        assert df_clean["a"].isna().sum() == 0
        assert df_clean["a"].iloc[2] == 2.0  # Forward filled from index 1

    def test_impute_mean(self, sample_df):
        """Test mean imputation."""
        reporter = NaNReporter()
        df_clean = reporter.impute_missing(sample_df, method="mean")

        # Column 'a' should have NaN filled with mean
        assert df_clean["a"].isna().sum() == 0
        expected_mean = (1.0 + 2.0 + 4.0 + 5.0) / 4
        assert df_clean["a"].iloc[2] == expected_mean

    def test_impute_zero(self, sample_df):
        """Test zero imputation."""
        reporter = NaNReporter()
        df_clean = reporter.impute_missing(sample_df, method="zero")

        assert df_clean["a"].iloc[2] == 0.0
        assert df_clean["d"].sum() == 0.0

    def test_get_problematic_columns(self, sample_df):
        """Test identifying problematic columns."""
        reporter = NaNReporter()
        reporter.scan_dataframe(sample_df)

        # Columns with >50% NaNs
        problematic = reporter.get_problematic_columns(threshold_pct=50.0)
        assert "d" in problematic  # 100% NaNs
        assert "b" in problematic  # 60% NaNs
        assert "a" not in problematic  # 20% NaNs

    def test_suggest_imputation(self, sample_df):
        """Test imputation suggestion."""
        reporter = NaNReporter()

        # Column 'd' has too many NaNs
        method, reason = reporter.suggest_imputation(sample_df, "d")
        assert method == "drop"

        # Column 'a' has few NaNs
        method, reason = reporter.suggest_imputation(sample_df, "a")
        assert method in ["mean", "median", "ffill", "interpolate"]

    def test_consecutive_nans(self, sample_df):
        """Test consecutive NaN detection."""
        reporter = NaNReporter()
        report = reporter.scan_dataframe(sample_df)

        # Column 'b' has 3 consecutive NaNs
        assert report.column_reports["b"].consecutive_nan_max == 3

        # Column 'd' has 5 consecutive NaNs
        assert report.column_reports["d"].consecutive_nan_max == 5

    def test_clear_reports(self, sample_df):
        """Test clearing reports."""
        reporter = NaNReporter()
        reporter.scan_dataframe(sample_df)
        assert reporter.last_report is not None

        reporter.clear_reports()
        assert reporter.last_report is None
        assert len(reporter.reports) == 0


class TestColumnReport:
    """Tests for ColumnReport dataclass."""

    def test_is_clean(self):
        """Test is_clean property."""
        clean = ColumnReport("test", 100, 0, 0.0)
        assert clean.is_clean

        dirty = ColumnReport("test", 100, 5, 5.0)
        assert not dirty.is_clean

    def test_severity(self):
        """Test severity property."""
        assert ColumnReport("a", 100, 0, 0.0).severity == "clean"
        assert ColumnReport("b", 100, 3, 3.0).severity == "low"
        assert ColumnReport("c", 100, 10, 10.0).severity == "medium"
        assert ColumnReport("d", 100, 50, 50.0).severity == "high"


class TestDataFrameReport:
    """Tests for DataFrameReport dataclass."""

    def test_overall_nan_percentage(self):
        """Test overall NaN percentage calculation."""
        from datetime import datetime

        report = DataFrameReport(
            timestamp=datetime.now(),
            total_rows=100,
            total_columns=10,
            total_nans=50,
            columns_with_nans=3,
        )
        assert report.overall_nan_percentage == 5.0  # 50 / 1000 * 100

    def test_is_clean(self):
        """Test is_clean property."""
        from datetime import datetime

        clean = DataFrameReport(
            timestamp=datetime.now(),
            total_rows=100,
            total_columns=10,
            total_nans=0,
            columns_with_nans=0,
        )
        assert clean.is_clean

        dirty = DataFrameReport(
            timestamp=datetime.now(),
            total_rows=100,
            total_columns=10,
            total_nans=5,
            columns_with_nans=1,
        )
        assert not dirty.is_clean
