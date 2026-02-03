"""Standardized data cleaning for all OHLC sources (Supabase, Kaggle, etc.)."""

import pandas as pd
import numpy as np
from typing import Optional


class DataCleaner:
    """Clean and standardize OHLC data from any source."""

    @staticmethod
    def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names to lowercase and common names."""
        df = df.copy()
        column_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Date": "date",
            "Timestamp": "ts",
            "timestamp": "ts",
        }
        for old, new in column_map.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        df.columns = df.columns.str.lower()
        if "date" in df.columns and "ts" not in df.columns:
            df = df.rename(columns={"date": "ts"})
        return df

    @staticmethod
    def remove_duplicates(df: pd.DataFrame, date_col: str = "ts") -> pd.DataFrame:
        """Remove duplicate timestamps (keep last)."""
        df = df.copy()
        if date_col in df.columns:
            df = df.drop_duplicates(subset=[date_col], keep="last")
        return df

    @staticmethod
    def fill_missing_volume(df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing/zero volume with forward fill or median."""
        df = df.copy()
        if "volume" not in df.columns:
            return df
        vol = df["volume"].replace(0, np.nan)
        vol = vol.ffill().fillna(vol.median()).fillna(1)
        df["volume"] = vol
        return df

    @staticmethod
    def fix_ohlc_logic(df: pd.DataFrame) -> pd.DataFrame:
        """Fix OHLC relationship violations."""
        df = df.copy()
        swap_mask = df["high"] < df["low"]
        df.loc[swap_mask, ["high", "low"]] = df.loc[swap_mask, ["low", "high"]].values
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"] = df[["low", "open", "close"]].min(axis=1)
        return df

    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame,
        method: str = "ffill",
        max_na_pct: float = 0.5,
    ) -> pd.DataFrame:
        """Fill or drop missing values in OHLC. Default: forward fill then backward fill."""
        df = df.copy()
        ohlc = [c for c in ["open", "high", "low", "close"] if c in df.columns]
        if not ohlc:
            return df
        if method == "ffill":
            df[ohlc] = df[ohlc].ffill().bfill()
        # Drop rows that are still NaN in critical columns if too many
        na_per_row = df[ohlc].isna().sum(axis=1)
        if na_per_row.sum() > 0 and (na_per_row > 0).mean() <= max_na_pct:
            df = df.dropna(subset=ohlc)
        return df

    @staticmethod
    def detect_outliers(
        df: pd.DataFrame,
        z_threshold: float = 3.0,
        date_col: str = "ts",
    ) -> pd.DataFrame:
        """Add is_outlier column (True where return z-score exceeds threshold). Does not remove rows."""
        df = df.copy()
        returns = df["close"].pct_change()
        std = returns.std()
        if std == 0 or pd.isna(std):
            df["is_outlier"] = False
            return df
        z_scores = (returns - returns.mean()) / std
        df["is_outlier"] = (z_scores.abs() > z_threshold).fillna(False)
        return df

    @staticmethod
    def remove_outliers(
        df: pd.DataFrame,
        z_threshold: float = 8.0,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """Remove only EXTREME return outliers (probable data errors)."""
        df = df.copy()
        returns = df["close"].pct_change()
        std = returns.std()
        if std == 0 or pd.isna(std):
            return df
        z_scores = (returns - returns.mean()) / std
        outliers = (z_scores.abs() > z_threshold).fillna(False)
        n_outliers = outliers.sum()
        if n_outliers > 0 and verbose:
            print(f"Removing {n_outliers} extreme outliers (|z| > {z_threshold})")
        return df.loc[~outliers].reset_index(drop=True)

    @classmethod
    def clean_all(
        cls,
        df: pd.DataFrame,
        remove_extreme_outliers: bool = True,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """Apply all cleaning steps."""
        if verbose:
            print(f"Starting with {len(df)} rows")
        df = cls.standardize_columns(df)
        df = cls.remove_duplicates(df)
        df = cls.fill_missing_volume(df)
        df = cls.fix_ohlc_logic(df)
        if remove_extreme_outliers:
            df = cls.remove_outliers(df, z_threshold=8.0, verbose=verbose)
        if verbose:
            print(f"Cleaned to {len(df)} rows")
        return df


def clean_supabase_data(
    symbol: str,
    timeframe: str = "d1",
    limit: int = 600,
    verbose: bool = True,
) -> pd.DataFrame:
    """Fetch and clean Supabase OHLC data."""
    from src.data.supabase_db import SupabaseDatabase

    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=limit)
    return DataCleaner.clean_all(df, verbose=verbose)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    print("Testing DataCleaner on Supabase NVDA data...")
    df_clean = clean_supabase_data("NVDA", limit=600)
    print(f"\n✅ Final cleaned {len(df_clean)} rows")
    if "ts" in df_clean.columns:
        print(f"Date range: {df_clean['ts'].min()} → {df_clean['ts'].max()}")
