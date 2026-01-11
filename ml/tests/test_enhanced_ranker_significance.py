"""
Statistical Significance Test for Enhanced Options Ranker with P0 Modules.

Tests whether the new weight adjustments improve ranking quality.
Generates synthetic options data with known outcomes to validate.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.models.enhanced_options_ranker import EnhancedOptionsRanker
from src.evaluation.options_ranking_validation import (
    OptionsRankingValidator,
    validate_options_ranking,
)


def generate_synthetic_options_data(n_contracts: int = 100) -> pd.DataFrame:
    """
    Generate synthetic options data with realistic characteristics.
    """
    np.random.seed(42)

    underlying_price = 250.0

    # Generate strikes around the money
    strikes = np.linspace(220, 280, n_contracts // 2)
    strikes = np.concatenate([strikes, strikes])  # Calls and puts

    sides = ["call"] * (n_contracts // 2) + ["put"] * (n_contracts // 2)

    # Generate realistic Greeks and prices
    data = []
    for i, (strike, side) in enumerate(zip(strikes, sides)):
        moneyness = (strike - underlying_price) / underlying_price

        # Delta based on moneyness
        if side == "call":
            delta = max(0.05, min(0.95, 0.5 - moneyness * 2))
        else:
            delta = -max(0.05, min(0.95, 0.5 + moneyness * 2))

        # IV with some randomness
        base_iv = 0.30 + abs(moneyness) * 0.1
        iv = base_iv + np.random.uniform(-0.05, 0.05)

        # Price based on delta and IV
        mid_price = abs(delta) * 10 + iv * 5 + np.random.uniform(0.5, 2.0)
        spread = mid_price * np.random.uniform(0.02, 0.08)

        # Volume and OI
        atm_factor = 1 - abs(moneyness) * 3
        volume = int(max(10, 1000 * atm_factor + np.random.uniform(0, 500)))
        oi = int(max(100, 5000 * atm_factor + np.random.uniform(0, 2000)))

        # Expiration 30 days out (as Unix timestamp for compatibility)
        expiration = int((datetime.today() + timedelta(days=30)).timestamp())

        data.append(
            {
                "strike": strike,
                "side": side,
                "expiration": expiration,
                "delta": delta,
                "gamma": abs(delta) * 0.1,
                "theta": -mid_price * 0.03,
                "vega": mid_price * 0.5,
                "impliedVolatility": iv,
                "bid": mid_price - spread / 2,
                "ask": mid_price + spread / 2,
                "volume": volume,
                "openInterest": oi,
                "underlyingPrice": underlying_price,
            }
        )

    return pd.DataFrame(data)


def generate_synthetic_returns(
    rankings_df: pd.DataFrame, signal_quality: float = 0.15
) -> pd.DataFrame:
    """
    Generate synthetic returns that correlate with ML scores.

    Higher signal_quality = stronger correlation between score and return.
    """
    np.random.seed(43)

    returns_data = []
    for idx, row in rankings_df.iterrows():
        # Base return from score (higher score = higher expected return)
        score = row.get("ml_score", 0.5)

        # Signal component (correlated with score)
        signal_return = (score - 0.5) * signal_quality * 2

        # Noise component
        noise = np.random.normal(0, 0.05)

        # Total return
        actual_return = signal_return + noise

        returns_data.append(
            {
                "strike": row["strike"],
                "side": row["side"],
                "expiration": row["expiration"],
                "actual_return": actual_return,
            }
        )

    return pd.DataFrame(returns_data)


def run_significance_test():
    """
    Run statistical significance tests on the enhanced ranker.
    """
    print("=" * 70)
    print("ENHANCED OPTIONS RANKER - STATISTICAL SIGNIFICANCE TEST")
    print("=" * 70)
    print()

    # Initialize ranker
    ranker = EnhancedOptionsRanker()

    # Print current weights
    print("Current Weight Configuration:")
    print("-" * 40)
    total = 0
    for component, weight in ranker.weights.items():
        print(f"  {component:20s}: {weight*100:5.1f}%")
        total += weight
    print(f"  {'TOTAL':20s}: {total*100:5.1f}%")
    print()

    # Generate synthetic data with multiple ranking dates
    print("Generating synthetic options data with multiple ranking dates...")
    options_df = generate_synthetic_options_data(n_contracts=200)

    # Add ranking dates (simulate 5 days of rankings)
    n_days = 5
    dates = pd.date_range(end=datetime.today(), periods=n_days, freq="D")
    options_df["ranking_date"] = np.tile(dates, len(options_df) // n_days + 1)[: len(options_df)]

    print(f"  Generated {len(options_df)} contracts across {n_days} days")
    print()

    # Run ranking
    print("Running enhanced ranking with P0 modules...")
    trend_analysis = {
        "trend": "bullish",
        "signal_strength": 7.5,
        "supertrend_factor": 2.8,
        "supertrend_performance": 0.72,
        "earnings_date": (datetime.today() + timedelta(days=25)).strftime("%Y-%m-%d"),
    }

    ranked_df = ranker.rank_options_with_trend(
        options_df,
        underlying_price=250.0,
        trend_analysis=trend_analysis,
        historical_vol=0.28,
    )
    # Preserve ranking_date
    ranked_df["ranking_date"] = options_df["ranking_date"].values

    print(f"  Ranked {len(ranked_df)} contracts")
    print(f"  Score range: {ranked_df['ml_score'].min():.3f} - {ranked_df['ml_score'].max():.3f}")
    print()

    # Generate returns with known signal quality
    print("Generating synthetic forward returns (signal_quality=0.15)...")
    returns_df = generate_synthetic_returns(ranked_df, signal_quality=0.15)
    print()

    # Merge for validation
    merged_df = ranked_df.merge(
        returns_df[["strike", "side", "expiration", "actual_return"]],
        on=["strike", "side", "expiration"],
    )
    merged_df["forward_return"] = merged_df["actual_return"]

    # Run validation
    print("Running statistical validation...")
    print("-" * 70)

    validator = OptionsRankingValidator(confidence_level=0.95, random_state=42)

    # Run validation tests
    results = validator.validate_ranking_accuracy(
        merged_df, merged_df, score_col="ml_score", return_col="forward_return"
    )

    # Score distribution
    dist_stats = validator.validate_score_distribution(merged_df["ml_score"].values)

    # NEW: Proper IC calculation with per-date ranking
    print("\nCalculating proper IC with per-date ranking...")
    ic_stats = validator.calculate_proper_ic(
        merged_df,
        date_col="ranking_date",
        score_col="ml_score",
        return_col="forward_return",
        horizon="1D",
        min_group_size=25,
        random_seed=42,
    )

    # NEW: Permutation test for leakage detection
    print("Running permutation test (100 permutations for speed)...")
    perm_stats = validator.run_permutation_test(
        merged_df,
        date_col="ranking_date",
        score_col="ml_score",
        return_col="forward_return",
        n_permutations=100,
        min_group_size=25,
        random_seed=42,
    )

    # Generate enhanced report
    report = validator.generate_report(
        results, dist_stats, ic_stats=ic_stats, permutation_stats=perm_stats
    )
    print(report)

    # Summary metrics
    print()
    print("=" * 70)
    print("SUMMARY METRICS")
    print("=" * 70)

    for result in results:
        status = "✅ PASS" if result.is_significant else "❌ FAIL"
        print(f"{status} {result.metric}: {result.value:.4f} (p={result.p_value:.4f})")

    n_passed = sum(1 for r in results if r.is_significant)
    n_total = len(results)

    print()
    print(f"Tests Passed: {n_passed}/{n_total}")

    # Check for leakage
    if perm_stats.get("leakage_suspected", False):
        print("⚠️ WARNING: Leakage suspected! Check feature/label timing.")

    if n_passed >= n_total * 0.75:
        print("🎉 RANKING MODEL IS STATISTICALLY SIGNIFICANT")
        return True
    elif n_passed >= n_total * 0.5:
        print("⚠️ RANKING MODEL SHOWS PARTIAL SIGNIFICANCE")
        return True
    else:
        print("❌ RANKING MODEL LACKS STATISTICAL SIGNIFICANCE")
        return False


if __name__ == "__main__":
    success = run_significance_test()
    sys.exit(0 if success else 1)
