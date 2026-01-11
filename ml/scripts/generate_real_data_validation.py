#!/usr/bin/env python3
"""
Generate real-data validation reports from Supabase options data.

This script queries options_price_history and options_ranks tables to:
1. Build a dataset with ml_score and forward_return
2. Run the enhanced OptionsRankingValidator
3. Generate reports for baseline vs Option C comparison

Usage:
    python scripts/generate_real_data_validation.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from config.settings import settings
from src.data.supabase_db import db
from src.evaluation import OptionsRankingValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_options_rankings_with_returns(days_back: int = 120) -> pd.DataFrame:
    """
    Fetch options rankings with forward returns from Supabase.

    Uses options_chain_snapshots table which now includes ml_score.
    Calculates 1-day forward returns by joining consecutive snapshots.

    Args:
        days_back: Number of days of history to fetch

    Returns:
        DataFrame with columns: ranking_date, ml_score, forward_return, etc.
    """
    logger.info(f"Fetching options data for last {days_back} days...")

    try:
        # Fetch options_chain_snapshots with ml_score
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        response = (
            db.client.table("options_chain_snapshots")
            .select("*, symbols!inner(ticker)")
            .gte("snapshot_date", cutoff_date)
            .not_.is_("ml_score", "null")
            .not_.is_("mark", "null")
            .order("snapshot_date", desc=False)
            .execute()
        )

        if not response.data:
            logger.warning("No options_chain_snapshots data found")
            return pd.DataFrame()

        df = pd.DataFrame(response.data)
        logger.info(f"Fetched {len(df)} raw options snapshots")

        # Extract underlying symbol from nested symbols object
        df["underlying_symbol"] = df["symbols"].apply(
            lambda x: x["ticker"] if isinstance(x, dict) else None
        )

        # Create contract key for grouping
        df["contract_key"] = (
            df["underlying_symbol_id"].astype(str)
            + "_"
            + df["expiry"].astype(str)
            + "_"
            + df["strike"].astype(str)
            + "_"
            + df["side"].astype(str)
        )

        # Sort and calculate forward returns
        df = df.sort_values(["contract_key", "snapshot_date"])

        # Calculate next day's mark price
        df["next_mark"] = df.groupby("contract_key")["mark"].shift(-1)
        df["next_date"] = df.groupby("contract_key")["snapshot_date"].shift(-1)

        # Filter to only consecutive day pairs
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
        df["next_date"] = pd.to_datetime(df["next_date"]).dt.date

        # Calculate days difference
        df["days_diff"] = df.apply(
            lambda row: (
                (row["next_date"] - row["snapshot_date"]).days
                if pd.notna(row["next_date"])
                else None
            ),
            axis=1,
        )

        # Keep only 1-day forward returns (consecutive trading days)
        df = df[df["days_diff"] == 1].copy()

        if df.empty:
            logger.warning("No consecutive day pairs found for forward returns")
            return pd.DataFrame()

        # Calculate forward return
        df["forward_return"] = (df["next_mark"] - df["mark"]) / df["mark"]

        # Rename for validator
        df["ranking_date"] = df["snapshot_date"]

        # Select relevant columns
        result = df[
            [
                "ranking_date",
                "underlying_symbol",
                "contract_key",
                "strike",
                "side",
                "expiry",
                "mark",
                "ml_score",
                "next_mark",
                "forward_return",
            ]
        ].copy()

        # Remove any rows with missing data
        result = result.dropna(subset=["ml_score", "forward_return"])

        logger.info(f"Processed {len(result)} contracts with forward returns")
        if not result.empty:
            logger.info(
                f"Date range: {result['ranking_date'].min()} to {result['ranking_date'].max()}"
            )
            logger.info(f"Unique days: {result['ranking_date'].nunique()}")

        return result

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise


def run_validation_report(df: pd.DataFrame, report_name: str = "Real Data") -> str:
    """
    Run the enhanced validator on real data and generate report.

    Args:
        df: DataFrame with ranking_date, ml_score, forward_return
        report_name: Name for the report header

    Returns:
        Validation report string
    """
    if df.empty:
        return f"No data available for {report_name} report"

    logger.info(f"Running validation for: {report_name}")
    logger.info(f"  Contracts: {len(df)}")
    logger.info(f"  Days: {df['ranking_date'].nunique()}")

    # Initialize validator with production thresholds
    validator = OptionsRankingValidator(
        confidence_level=0.95,
        hit_rate_warning_n_threshold=200,
        low_std_warning_threshold=0.01,
        min_days_threshold=20,
    )

    # Run standard validation tests
    results = validator.validate_ranking_accuracy(
        rankings_df=df,
        returns_df=df,
        score_col="ml_score",
        return_col="forward_return",
        n_quantiles=5,
    )

    # Analyze score distribution
    dist_stats = validator.analyze_score_distribution(df, score_col="ml_score")

    # Calculate proper IC with per-date ranking
    ic_stats = validator.calculate_proper_ic(
        df,
        date_col="ranking_date",
        score_col="ml_score",
        return_col="forward_return",
        horizon="1D",
        min_group_size=25,
        random_seed=42,
    )

    # Run permutation test with 1000 permutations for meaningful p-value
    perm_stats = validator.run_permutation_test(
        df,
        date_col="ranking_date",
        score_col="ml_score",
        return_col="forward_return",
        n_permutations=1000,
        min_group_size=25,
        random_seed=42,
    )

    # Generate report
    report = validator.generate_report(
        results,
        dist_stats,
        ic_stats=ic_stats,
        permutation_stats=perm_stats,
    )

    # Add header
    header = f"\n{'='*60}\n{report_name.upper()} VALIDATION\n{'='*60}\n"

    return header + report


def main():
    """Main entry point."""
    print("=" * 70)
    print("REAL DATA VALIDATION REPORT GENERATOR")
    print("=" * 70)
    print()

    # Fetch real data from Supabase
    try:
        df = fetch_options_rankings_with_returns(days_back=120)
    except Exception as e:
        print(f"Error fetching data: {e}")
        print("\nMake sure SUPABASE_URL and SUPABASE_KEY are set in your environment.")
        return

    if df.empty:
        print("No data found in options_price_history table.")
        print("\nTo generate real data reports, you need:")
        print("  1. Options ranking jobs to have run (populating options_ranks)")
        print("  2. Options snapshots to be captured (populating options_price_history)")
        print("  3. At least 60 days of data (prefer 120)")
        return

    # Generate report with current weights
    report = run_validation_report(df, "Current Weights (Option C)")
    print(report)

    # Summary stats
    print("\n" + "=" * 70)
    print("DATA SUMMARY")
    print("=" * 70)
    print(f"Total contracts with forward returns: {len(df)}")
    print(f"Unique trading days: {df['ranking_date'].nunique()}")
    print(f"Date range: {df['ranking_date'].min()} to {df['ranking_date'].max()}")
    print(f"Unique underlyings: {df['underlying_symbol'].nunique()}")
    print(f"Mean forward return: {df['forward_return'].mean():.4f}")
    print(f"Std forward return: {df['forward_return'].std():.4f}")
    print(f"Mean ml_score: {df['ml_score'].mean():.4f}")


if __name__ == "__main__":
    main()
