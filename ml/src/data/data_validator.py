"""OHLC data validation and cleaning pipeline.

Validates OHLC data for common issues that can corrupt ML features:
1. OHLC relationship violations (High < max(Open, Close), etc.)
2. Negative or zero prices
3. Negative volume
4. Large gaps (> 3 ATR)
5. Extreme outliers (Z-score > 4)
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    issues: List[str]
    rows_flagged: int
    rows_removed: int


class OHLCValidator:
    """
    Validates OHLC data for common issues.

    Checks:
    1. OHLC relationship: High >= max(Open, Close), Low <= min(Open, Close)
    2. Volume positivity: Volume >= 0
    3. Price positivity: All prices > 0
    4. Gap detection: Flags gaps > 3 ATR from previous close
    5. Outlier detection: Z-score > 4 on returns
    """

    MAX_GAP_ATRS = 3.0
    OUTLIER_ZSCORE = 4.0

    def validate(
        self,
        df: pd.DataFrame,
        fix_issues: bool = True,
    ) -> Tuple[pd.DataFrame, ValidationResult]:
        """
        Validate and optionally fix OHLC data.

        Args:
            df: DataFrame with open, high, low, close, volume columns
            fix_issues: If True, remove/fix invalid rows

        Returns:
            Tuple of (cleaned DataFrame, ValidationResult)
        """
        issues = []
        original_len = len(df)
        flagged_rows = set()
        df = df.copy()

        # Normalize column names to lowercase
        df.columns = df.columns.str.lower()

        # 1. Check OHLC relationships
        if all(col in df.columns for col in ["open", "high", "low", "close"]):
            invalid_high = df["high"] < df[["open", "close"]].max(axis=1)
            invalid_low = df["low"] > df[["open", "close"]].min(axis=1)

            if invalid_high.any():
                issues.append(f"High < max(Open,Close) in {invalid_high.sum()} rows")
                flagged_rows.update(df[invalid_high].index.tolist())

            if invalid_low.any():
                issues.append(f"Low > min(Open,Close) in {invalid_low.sum()} rows")
                flagged_rows.update(df[invalid_low].index.tolist())

        # 2. Check volume
        if "volume" in df.columns:
            negative_volume = df["volume"] < 0
            if negative_volume.any():
                issues.append(f"Negative volume in {negative_volume.sum()} rows")
                flagged_rows.update(df[negative_volume].index.tolist())

        # 3. Check price positivity
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if col in df.columns:
                non_positive = df[col] <= 0
                if non_positive.any():
                    issues.append(f"Non-positive {col} in {non_positive.sum()} rows")
                    flagged_rows.update(df[non_positive].index.tolist())

        # 4. Gap detection (skip first row)
        large_gaps = pd.Series(False, index=df.index)
        if len(df) > 1 and "open" in df.columns and "close" in df.columns:
            atr = self._calculate_atr(df, period=14)
            gaps = (df["open"].iloc[1:] - df["close"].iloc[:-1].values).abs()
            atr_aligned = atr.iloc[1:]

            # Avoid division by zero
            valid_atr = atr_aligned > 0
            if valid_atr.any():
                large_gaps_mask = pd.Series(False, index=df.index[1:], dtype=bool)
                large_gaps_mask.loc[valid_atr] = (
                    gaps[valid_atr] > (atr_aligned[valid_atr] * self.MAX_GAP_ATRS)
                ).astype(bool)
                large_gaps = pd.Series(False, index=df.index, dtype=bool)
                large_gaps.iloc[1:] = large_gaps_mask.values

                if large_gaps.any():
                    gap_indices = df.index[large_gaps]
                    issues.append(
                        f"Large gaps (>{self.MAX_GAP_ATRS} ATR) in {len(gap_indices)} rows"
                    )
                    # Don't remove gaps, just flag for awareness

        # 5. Outlier detection on returns
        if "close" in df.columns and len(df) > 10:
            returns = df["close"].pct_change()
            returns_std = returns.std()
            if returns_std > 0:
                zscore = (returns - returns.mean()) / returns_std
                outliers = zscore.abs() > self.OUTLIER_ZSCORE
                if outliers.any():
                    issues.append(
                        f"Return outliers (z>{self.OUTLIER_ZSCORE}) in {outliers.sum()} rows"
                    )
                    flagged_rows.update(df[outliers].index.tolist())

        # Apply fixes if requested
        rows_removed = 0
        if fix_issues and flagged_rows:
            # Remove flagged rows (except gaps which are just informational)
            gap_indices = set(df.index[large_gaps]) if large_gaps.any() else set()
            removable = flagged_rows - gap_indices
            if removable:
                df = df.drop(index=list(removable), errors="ignore")
                rows_removed = original_len - len(df)
                logger.info(f"Removed {rows_removed} invalid rows from data")

        if issues:
            logger.warning(f"Data validation issues: {issues}")
        else:
            logger.debug(f"Data validation passed for {len(df)} rows")

        return df, ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            rows_flagged=len(flagged_rows),
            rows_removed=rows_removed,
        )

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)

        tr = pd.concat(
            [
                high - low,
                (high - close).abs(),
                (low - close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return tr.rolling(window=period).mean()

    def get_data_quality_score(self, df: pd.DataFrame) -> float:
        """
        Calculate overall data quality score (0-1).

        Args:
            df: DataFrame to assess

        Returns:
            Quality score where 1.0 = perfect data
        """
        _, result = self.validate(df, fix_issues=False)

        if len(df) == 0:
            return 0.0

        # Score based on percentage of clean rows
        flagged_pct = result.rows_flagged / len(df)
        score = max(0.0, 1.0 - flagged_pct)

        return score


def validate_ohlc_data(
    df: pd.DataFrame,
    fix_issues: bool = True,
) -> Tuple[pd.DataFrame, ValidationResult]:
    """
    Convenience function to validate OHLC data.

    Args:
        df: DataFrame with OHLC data
        fix_issues: If True, remove invalid rows

    Returns:
        Tuple of (cleaned DataFrame, ValidationResult)
    """
    validator = OHLCValidator()
    return validator.validate(df, fix_issues=fix_issues)
