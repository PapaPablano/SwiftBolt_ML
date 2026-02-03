"""
Load OHLCV data from the Kaggle dataset: borismarjanovic/price-volume-data-for-all-us-stocks-etfs.

Dataset columns: Date, Open, High, Low, Close, Volume, OpenInt.
Returns DataFrames with: ts, open, high, low, close, volume (compatible with fetch_ohlc_bars).

Requires: pip install kagglehub
Kaggle API: set KAGGLE_USERNAME and KAGGLE_KEY, or place kaggle.json in ~/.kaggle/

Usage:
    from src.data.kaggle_stock_data import get_kaggle_path, load_symbol_ohlcv

    path = get_kaggle_path()
    df = load_symbol_ohlcv("AAPL", path=path, limit=600)

    # Or run walk-forward with Kaggle data:
    #   python walk_forward_weekly.py AAPL --kaggle --horizon 5 --threshold 0.02
"""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

KAGGLE_DATASET = "borismarjanovic/price-volume-data-for-all-us-stocks-etfs"

# Column mapping: dataset -> our standard (ts, open, high, low, close, volume)
COL_MAP = {
    "Date": "ts",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


def get_kaggle_path(force_download: bool = False) -> str:
    """
    Download the Kaggle price-volume dataset and return the path to its files.

    Args:
        force_download: If True, re-download even if cached.

    Returns:
        Path to the dataset root (contains Stocks/, ETFs/ or similar).
    """
    try:
        import kagglehub
    except ImportError:
        raise ImportError(
            "kagglehub is required for Kaggle data. Install with: pip install kagglehub"
        )
    path = kagglehub.dataset_download(KAGGLE_DATASET)
    logger.info("Kaggle dataset path: %s", path)
    return path


def _find_symbol_file(symbol: str, root: str) -> Optional[str]:
    """Find CSV or TXT file for symbol under root. Returns first match or None."""
    symbol_upper = symbol.upper()
    symbol_lower = symbol.lower()
    root_path = Path(root)

    # Common patterns: Stocks/aapl.us.txt, Data/Stocks/AAPL.csv, AAPL.us.txt, etc.
    candidates = []
    for ext in ("*.csv", "*.txt"):
        for f in root_path.rglob(ext):
            name = f.stem  # e.g. aapl.us or AAPL
            if name.upper() == symbol_upper or name.lower() == symbol_lower:
                candidates.append(str(f))
            # e.g. aapl.us.txt -> aapl.us
            if "." in name and name.split(".")[0].upper() == symbol_upper:
                candidates.append(str(f))

    # Prefer exact match then alphabetically first
    if candidates:
        return min(candidates, key=len)
    return None


def load_symbol_ohlcv(
    symbol: str,
    path: Optional[str] = None,
    limit: Optional[int] = None,
    timeframe: str = "d1",
) -> Optional[pd.DataFrame]:
    """
    Load OHLCV for a symbol from the Kaggle price-volume dataset.

    Args:
        symbol: Ticker (e.g. AAPL, TSLA).
        path: Dataset root path from get_kaggle_path(). If None, calls get_kaggle_path().
        limit: Max number of rows (most recent). None = all.
        timeframe: Ignored (dataset is daily only); kept for API compatibility.

    Returns:
        DataFrame with columns ts, open, high, low, close, volume (sorted by ts ascending),
        or None if symbol file not found.
    """
    if path is None:
        path = get_kaggle_path()
    if not os.path.isdir(path):
        logger.warning("Kaggle path is not a directory: %s", path)
        return None

    file_path = _find_symbol_file(symbol, path)
    if not file_path:
        logger.warning("No file found for symbol %s under %s", symbol, path)
        return None

    # Read CSV or TXT (often comma-separated)
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.warning("Failed to read %s: %s", file_path, e)
        return None

    # Normalize column names (dataset uses Date, Open, High, Low, Close, Volume)
    rename = {}
    for old, new in COL_MAP.items():
        if old in df.columns:
            rename[old] = new
    if not rename:
        # Try lowercase
        for old, new in COL_MAP.items():
            if old.lower() in [c.lower() for c in df.columns]:
                for c in df.columns:
                    if c.lower() == old.lower():
                        rename[c] = new
                        break
    if not rename:
        logger.warning("Expected columns (Date, Open, High, Low, Close, Volume) not found in %s", file_path)
        return None

    df = df.rename(columns=rename)
    required = {"ts", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        logger.warning("Missing columns after rename: %s", set(required) - set(df.columns))
        return None

    df = df[list(required)].copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.dropna(subset=["ts", "close"])
    df = df.sort_values("ts").reset_index(drop=True)

    if limit is not None and len(df) > limit:
        df = df.tail(limit).reset_index(drop=True)

    logger.info("Loaded %s bars for %s from Kaggle", len(df), symbol)
    return df
