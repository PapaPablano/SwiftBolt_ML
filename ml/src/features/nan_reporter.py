"""
NaN Reporter: Track and report missing data in DataFrames.

This utility helps identify data quality issues by:
1. Scanning DataFrames for NaN/null values
2. Generating detailed reports by column
3. Providing imputation methods
4. Tracking data quality over time

Usage:
    reporter = NaNReporter()
    summary = reporter.scan_dataframe(df)
    print(reporter.get_report())
    df_clean = reporter.impute_missing(df, method="ffill")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ColumnReport:
    """Report for a single column's NaN status."""

    column_name: str
    total_rows: int
    nan_count: int
    nan_percentage: float
    first_nan_index: Optional[int] = None
    last_nan_index: Optional[int] = None
    consecutive_nan_max: int = 0

    @property
    def is_clean(self) -> bool:
        return self.nan_count == 0

    @property
    def severity(self) -> str:
        if self.nan_percentage == 0:
            return "clean"
        elif self.nan_percentage < 5:
            return "low"
        elif self.nan_percentage < 20:
            return "medium"
        else:
            return "high"


@dataclass
class DataFrameReport:
    """Complete report for a DataFrame's data quality."""

    timestamp: datetime
    total_rows: int
    total_columns: int
    total_nans: int
    columns_with_nans: int
    column_reports: Dict[str, ColumnReport] = field(default_factory=dict)

    @property
    def overall_nan_percentage(self) -> float:
        total_cells = self.total_rows * self.total_columns
        if total_cells == 0:
            return 0.0
        return (self.total_nans / total_cells) * 100

    @property
    def is_clean(self) -> bool:
        return self.total_nans == 0

    @property
    def severity(self) -> str:
        if self.overall_nan_percentage == 0:
            return "clean"
        elif self.overall_nan_percentage < 1:
            return "low"
        elif self.overall_nan_percentage < 5:
            return "medium"
        else:
            return "high"


class NaNReporter:
    """
    Track and report missing data in DataFrames.

    Provides comprehensive NaN analysis and imputation utilities.
    """

    def __init__(self):
        self.reports: List[DataFrameReport] = []
        self.last_report: Optional[DataFrameReport] = None

    def scan_dataframe(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
    ) -> DataFrameReport:
        """
        Scan a DataFrame for NaN values and generate a report.

        Args:
            df: DataFrame to scan
            columns: Optional list of columns to scan (default: all)

        Returns:
            DataFrameReport with detailed NaN analysis
        """
        if columns is None:
            columns = df.columns.tolist()

        column_reports = {}
        total_nans = 0
        columns_with_nans = 0

        for col in columns:
            if col not in df.columns:
                continue

            series = df[col]
            nan_mask = series.isna()
            nan_count = nan_mask.sum()
            total_nans += nan_count

            if nan_count > 0:
                columns_with_nans += 1
                first_nan = nan_mask.idxmax() if nan_mask.any() else None
                last_nan = nan_mask[::-1].idxmax() if nan_mask.any() else None
                consecutive_max = self._max_consecutive_nans(nan_mask)
            else:
                first_nan = None
                last_nan = None
                consecutive_max = 0

            column_reports[col] = ColumnReport(
                column_name=col,
                total_rows=len(series),
                nan_count=nan_count,
                nan_percentage=(nan_count / len(series) * 100) if len(series) > 0 else 0,
                first_nan_index=first_nan,
                last_nan_index=last_nan,
                consecutive_nan_max=consecutive_max,
            )

        report = DataFrameReport(
            timestamp=datetime.now(),
            total_rows=len(df),
            total_columns=len(columns),
            total_nans=total_nans,
            columns_with_nans=columns_with_nans,
            column_reports=column_reports,
        )

        self.reports.append(report)
        self.last_report = report

        logger.info(
            f"NaN scan complete: {total_nans} NaNs in {columns_with_nans}/{len(columns)} columns "
            f"({report.overall_nan_percentage:.2f}% overall)"
        )

        return report

    def _max_consecutive_nans(self, nan_mask: pd.Series) -> int:
        """Find the maximum number of consecutive NaN values."""
        if not nan_mask.any():
            return 0

        groups = (nan_mask != nan_mask.shift()).cumsum()
        consecutive = nan_mask.groupby(groups).sum()
        return int(consecutive.max()) if len(consecutive) > 0 else 0

    def get_report(self, report: Optional[DataFrameReport] = None) -> str:
        """
        Generate a human-readable report string.

        Args:
            report: Report to format (default: last report)

        Returns:
            Formatted report string
        """
        if report is None:
            report = self.last_report

        if report is None:
            return "No report available. Run scan_dataframe() first."

        lines = [
            "=" * 60,
            "NaN REPORT",
            "=" * 60,
            f"Timestamp: {report.timestamp.isoformat()}",
            f"Total Rows: {report.total_rows:,}",
            f"Total Columns: {report.total_columns}",
            f"Total NaNs: {report.total_nans:,}",
            f"Overall NaN %: {report.overall_nan_percentage:.2f}%",
            f"Severity: {report.severity.upper()}",
            "",
            "COLUMNS WITH NANS:",
            "-" * 40,
        ]

        # Sort by NaN count descending
        sorted_cols = sorted(
            report.column_reports.values(),
            key=lambda x: x.nan_count,
            reverse=True,
        )

        for col_report in sorted_cols:
            if col_report.nan_count > 0:
                lines.append(
                    f"  {col_report.column_name}: "
                    f"{col_report.nan_count:,} NaNs ({col_report.nan_percentage:.1f}%) "
                    f"[{col_report.severity}]"
                )

        if report.columns_with_nans == 0:
            lines.append("  (none - data is clean)")

        lines.append("=" * 60)

        return "\n".join(lines)

    def get_report_dataframe(
        self,
        report: Optional[DataFrameReport] = None,
    ) -> pd.DataFrame:
        """
        Get report as a DataFrame for display in dashboards.

        Args:
            report: Report to convert (default: last report)

        Returns:
            DataFrame with column-level NaN statistics
        """
        if report is None:
            report = self.last_report

        if report is None:
            return pd.DataFrame()

        data = []
        for col_report in report.column_reports.values():
            data.append(
                {
                    "column": col_report.column_name,
                    "nan_count": col_report.nan_count,
                    "nan_pct": col_report.nan_percentage,
                    "severity": col_report.severity,
                    "max_consecutive": col_report.consecutive_nan_max,
                }
            )

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("nan_count", ascending=False)

        return df

    def impute_missing(
        self,
        df: pd.DataFrame,
        method: str = "ffill",
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Impute missing values in a DataFrame.

        Args:
            df: DataFrame to impute
            method: Imputation method:
                - 'ffill': Forward fill
                - 'bfill': Backward fill
                - 'mean': Column mean
                - 'median': Column median
                - 'zero': Fill with 0
                - 'interpolate': Linear interpolation
            columns: Columns to impute (default: all numeric)
            limit: Maximum consecutive NaNs to fill

        Returns:
            DataFrame with imputed values
        """
        df = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=["number"]).columns.tolist()

        original_nans = df[columns].isna().sum().sum()

        for col in columns:
            if col not in df.columns:
                continue

            if method == "ffill":
                df[col] = df[col].ffill(limit=limit)
            elif method == "bfill":
                df[col] = df[col].bfill(limit=limit)
            elif method == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif method == "median":
                df[col] = df[col].fillna(df[col].median())
            elif method == "zero":
                df[col] = df[col].fillna(0)
            elif method == "interpolate":
                df[col] = df[col].interpolate(method="linear", limit=limit)
            else:
                raise ValueError(f"Unknown imputation method: {method}")

        remaining_nans = df[columns].isna().sum().sum()
        filled = original_nans - remaining_nans

        logger.info(
            f"Imputed {filled:,} NaN values using '{method}' method "
            f"({remaining_nans:,} remaining)"
        )

        return df

    def get_problematic_columns(
        self,
        report: Optional[DataFrameReport] = None,
        threshold_pct: float = 10.0,
    ) -> List[str]:
        """
        Get list of columns with NaN percentage above threshold.

        Args:
            report: Report to check (default: last report)
            threshold_pct: NaN percentage threshold

        Returns:
            List of column names exceeding threshold
        """
        if report is None:
            report = self.last_report

        if report is None:
            return []

        return [
            col_report.column_name
            for col_report in report.column_reports.values()
            if col_report.nan_percentage >= threshold_pct
        ]

    def suggest_imputation(
        self,
        df: pd.DataFrame,
        col: str,
    ) -> Tuple[str, str]:
        """
        Suggest an imputation method for a column based on its characteristics.

        Args:
            df: DataFrame containing the column
            col: Column name

        Returns:
            Tuple of (method, reason)
        """
        if col not in df.columns:
            return ("none", "Column not found")

        series = df[col]

        # Check if time series (has datetime index or ts column)
        is_timeseries = isinstance(df.index, pd.DatetimeIndex) or "ts" in df.columns

        # Check distribution
        if series.dtype in ["object", "category"]:
            return ("ffill", "Categorical data - forward fill preserves last known value")

        nan_pct = series.isna().mean() * 100

        if nan_pct > 50:
            return ("drop", "Too many NaNs (>50%) - consider dropping column")

        if is_timeseries:
            # For time series, prefer interpolation or forward fill
            if nan_pct < 5:
                return ("interpolate", "Time series with few gaps - interpolation works well")
            else:
                return ("ffill", "Time series with gaps - forward fill preserves trend")

        # For non-time series
        skewness = series.skew() if series.notna().sum() > 2 else 0

        if abs(skewness) > 1:
            return ("median", "Skewed distribution - median is more robust")
        else:
            return ("mean", "Normal-ish distribution - mean is appropriate")

    def clear_reports(self):
        """Clear all stored reports."""
        self.reports = []
        self.last_report = None
        logger.info("Cleared all NaN reports")
