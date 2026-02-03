"""Relaxed OHLC validator for production trading.

Uses looser thresholds than OHLCValidator: gaps/outliers are often real market moves.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any


class RelaxedOHLCValidator:
    """Less strict validator for real market data."""

    def __init__(
        self,
        gap_threshold_atr: float = 5.0,  # Raised from 3.0
        outlier_z_threshold: float = 6.0,  # Raised from 4.0
        min_volume: int = 100,
    ):
        self.gap_threshold_atr = gap_threshold_atr
        self.outlier_z_threshold = outlier_z_threshold
        self.min_volume = min_volume

    def validate(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """Validate OHLC data with relaxed rules."""
        issues: Dict[str, Any] = {
            "missing_required_columns": [],
            "null_values": [],
            "negative_prices": [],
            "zero_volume": [],
            "ohlc_logic_errors": [],
            "large_gaps": [],
            "return_outliers": [],
        }

        # Normalize column names to lowercase for checks
        cols_lower = {c.lower(): c for c in df.columns}
        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in cols_lower]
        if missing:
            issues["missing_required_columns"] = missing
            return False, issues

        # Use lowercase column access
        df_check = df.copy()
        df_check.columns = df_check.columns.str.lower()

        # Check for nulls
        for col in required:
            nulls = df_check[col].isnull().sum()
            if nulls > 0:
                issues["null_values"].append(f"{col}: {nulls} nulls")

        # Check for negative prices
        for col in ["open", "high", "low", "close"]:
            negatives = (df_check[col] < 0).sum()
            if negatives > 0:
                issues["negative_prices"].append(f"{col}: {negatives} negative")

        # Check for zero volume
        zero_vol = (df_check["volume"] == 0).sum()
        if zero_vol > 0:
            issues["zero_volume"].append(f"{zero_vol} bars with zero volume")

        # Check OHLC logic (high >= low, etc.)
        bad_hl = (df_check["high"] < df_check["low"]).sum()
        if bad_hl > 0:
            issues["ohlc_logic_errors"].append(f"{bad_hl} bars with high < low")

        bad_hoc = (
            (df_check["high"] < df_check["open"]) | (df_check["high"] < df_check["close"])
        ).sum()
        if bad_hoc > 0:
            issues["ohlc_logic_errors"].append(f"{bad_hoc} bars with high < open/close")

        bad_loc = (
            (df_check["low"] > df_check["open"]) | (df_check["low"] > df_check["close"])
        ).sum()
        if bad_loc > 0:
            issues["ohlc_logic_errors"].append(f"{bad_loc} bars with low > open/close")

        # Check for large gaps (RELAXED)
        if len(df_check) > 1:
            atr = (df_check["high"] - df_check["low"]).rolling(14).mean()
            gaps = (df_check["open"] - df_check["close"].shift(1)).abs()
            threshold = atr * self.gap_threshold_atr
            large_gaps = (gaps > threshold).sum()
            if large_gaps > 0:
                issues["large_gaps"].append(
                    f"{large_gaps} gaps > {self.gap_threshold_atr}x ATR (informational)"
                )

        # Check for return outliers (RELAXED)
        returns = df_check["close"].pct_change()
        if len(returns) > 10 and returns.std() > 0:
            z_scores = (returns - returns.mean()) / returns.std()
            outliers = (z_scores.abs() > self.outlier_z_threshold).sum()
            if outliers > 0:
                issues["return_outliers"].append(
                    f"{outliers} returns with |z| > {self.outlier_z_threshold} (informational)"
                )

        # Determine validity (only fail on critical issues)
        critical_issues = (
            issues["missing_required_columns"]
            or issues["null_values"]
            or issues["negative_prices"]
            or issues["ohlc_logic_errors"]
        )
        is_valid = not critical_issues
        return is_valid, issues

    def fix_issues(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix critical issues. Keep gaps/outliers (they're real!)."""
        df_fixed = df.copy()
        if "ts" in df_fixed.columns:
            df_fixed = df_fixed.dropna(subset=["ts", "open", "high", "low", "close", "volume"])
        else:
            df_fixed = df_fixed.dropna(subset=["open", "high", "low", "close", "volume"])

        # Fix zero volume (replace with 1 to avoid division errors)
        if "volume" in df_fixed.columns:
            df_fixed.loc[df_fixed["volume"] == 0, "volume"] = 1

        # Fix OHLC logic errors
        swap_mask = df_fixed["high"] < df_fixed["low"]
        df_fixed.loc[swap_mask, ["high", "low"]] = df_fixed.loc[swap_mask, ["low", "high"]].values
        df_fixed["high"] = df_fixed[["high", "open", "close"]].max(axis=1)
        df_fixed["low"] = df_fixed[["low", "open", "close"]].min(axis=1)

        return df_fixed


def validate_and_fix(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Validate and fix OHLC data using relaxed rules."""
    validator = RelaxedOHLCValidator()
    is_valid, issues = validator.validate(df)

    if verbose:
        print(f"Initial validation: {'✅ VALID' if is_valid else '⚠️ HAS ISSUES'}")
        for category, items in issues.items():
            if items:
                print(f"  {category}: {items}")

    if not is_valid:
        if verbose:
            print("\nApplying fixes...")
        df_fixed = validator.fix_issues(df)
        is_valid_after, issues_after = validator.validate(df_fixed)
        if verbose:
            print(f"After fixes: {'✅ VALID' if is_valid_after else '⚠️ STILL HAS ISSUES'}")
            rows_removed = len(df) - len(df_fixed)
            if rows_removed > 0:
                print(f"Rows removed: {rows_removed}")
        return df_fixed

    return df


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.data.supabase_db import SupabaseDatabase

    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars("NVDA", timeframe="d1", limit=600)
    print("Testing RelaxedOHLCValidator on Supabase NVDA data...")
    df_clean = validate_and_fix(df, verbose=True)
    print(f"\n✅ Clean {len(df_clean)} rows")
