#!/usr/bin/env python3
"""
L1 Gate Validation - 15m 4-bar forecast vs no-change baseline.

Walk-forward evaluation with Diebold-Mariano statistical test.
Pass threshold: DM p-value < 0.05 AND mean(d) < 0.

Usage:
    python ml/scripts/l1_gate_validation.py --symbols AAPL,MSFT,SPY \
        --train-bars 500 --test-bars 50 --step-bars 25 \
        --output-dir validation_results

    Add INTC,F etc. if symbols are seeded in the symbols table.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import db
from src.evaluation.l1_gate_evaluator import L1GateEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="L1 gate validation: 15m 4-bar forecast vs no-change baseline"
    )
    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,SPY",
        help="Comma-separated symbols (default: AAPL,MSFT,SPY). Add INTC,F if in DB.",
    )
    parser.add_argument(
        "--train-bars",
        type=int,
        default=500,
        help="Training window size in bars (default: 500)",
    )
    parser.add_argument(
        "--test-bars",
        type=int,
        default=50,
        help="Test window size in bars (default: 50)",
    )
    parser.add_argument(
        "--step-bars",
        type=int,
        default=25,
        help="Step size for rolling windows (default: 25)",
    )
    parser.add_argument(
        "--max-origins",
        type=int,
        default=50,
        help="Max test origins per symbol (default: 50)",
    )
    parser.add_argument(
        "--limit-bars",
        type=int,
        default=3500,
        help="Max OHLC bars to fetch per symbol (default: 3500, ~5 months 15m)",
    )
    parser.add_argument(
        "--output-dir",
        default="validation_results",
        help="Output directory for report (default: validation_results)",
    )
    parser.add_argument(
        "--no-baseline-after-close",
        action="store_true",
        help="Use close[t-1] for baseline (production at open of bar t); "
        "default uses close[t] (production after bar t closes)",
    )
    parser.add_argument(
        "--min-bars-per-symbol",
        type=int,
        default=1000,
        help="Min bars per symbol for time coverage (~2+ months 15m; default: 1000)",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        logger.error("No symbols specified")
        return 1

    evaluator = L1GateEvaluator(
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        step_bars=args.step_bars,
        max_origins_per_symbol=args.max_origins,
        baseline_after_close_t=not args.no_baseline_after_close,
    )

    all_losses = []
    by_symbol = {}
    skipped_symbols: dict[str, str] = {}

    for symbol in symbols:
        logger.info("Loading %s m15 bars...", symbol)
        try:
            df = db.fetch_ohlc_bars(
                symbol, timeframe="m15", limit=args.limit_bars
            )
        except Exception as e:
            logger.error("Failed to fetch %s: %s", symbol, e)
            skipped_symbols[symbol] = f"fetch failed: {e!s}"
            continue

        if df is None or len(df) == 0:
            reason = (
                getattr(df, "attrs", {}).get("skip_reason", "0 bars returned")
                if df is not None and hasattr(df, "attrs")
                else "0 bars returned"
            )
            skipped_symbols[symbol] = reason
            logger.warning("No data for %s (%s)", symbol, reason)
            continue

        if len(df) < args.min_bars_per_symbol:
            skipped_symbols[symbol] = "insufficient time coverage"
            logger.warning(
                "%s: insufficient time coverage (%d bars < %d); need ~2+ months 15m",
                symbol,
                len(df),
                args.min_bars_per_symbol,
            )
            continue

        logger.info("Computing loss series for %s (%d bars)...", symbol, len(df))
        loss_df = evaluator.compute_loss_series(symbol, df)

        if len(loss_df) == 0:
            skipped_symbols[symbol] = "no valid origins"
            logger.warning("No valid origins for %s", symbol)
            continue

        all_losses.append(loss_df)
        by_symbol[symbol] = {
            "n_origins": len(loss_df),
            "mean_d": float(loss_df["d"].mean()),
            "mean_L_model": float(loss_df["L_model"].mean()),
            "mean_L_baseline": float(loss_df["L_baseline"].mean()),
        }

    if not all_losses:
        logger.error("No validation results generated")
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "l1_gate_report.json", "w") as f:
            json.dump(
                {
                    "symbols": symbols,
                    "skipped_symbols": skipped_symbols,
                    "by_symbol": {},
                    "error": "No validation results generated",
                },
                f,
                indent=2,
            )
        if skipped_symbols:
            print("Skipped symbols:")
            for sym, reason in skipped_symbols.items():
                print(f"  {sym}: {reason}")
        return 1

    combined = pd.concat(all_losses, ignore_index=True)
    dm_result = evaluator.run_dm_test(combined)

    # Power check: fail fast if insufficient sample size
    if dm_result.interpretation and "Insufficient sample size" in dm_result.interpretation:
        logger.error("Insufficient sample size: n_origins=%d < 100", len(combined))
        print("\n" + "=" * 60)
        print("L1 GATE VALIDATION FAILED")
        print("=" * 60)
        print("Insufficient sample size: pooled n_origins < 100")
        print("Run with more symbols or longer limit-bars to get reliable p-value.")
        print("=" * 60)
        return 1

    # Per-symbol sanity: require at least 3/5 symbols have mean(d) < 0
    n_symbols = len(by_symbol)
    n_symbols_positive = sum(1 for m in by_symbol.values() if m["mean_d"] < 0)
    min_positive_required = max(2, min(3, n_symbols) if n_symbols >= 3 else 1)
    per_symbol_ok = n_symbols_positive >= min_positive_required

    passes = (
        dm_result.is_significant
        and combined["d"].mean() < 0
        and per_symbol_ok
    )

    report = {
        "dm_statistic": dm_result.statistic,
        "dm_pvalue": dm_result.p_value,
        "dm_significant": dm_result.is_significant,
        "mean_d": float(combined["d"].mean()),
        "n_origins": len(combined),
        "symbols": symbols,
        "by_symbol": by_symbol,
        "skipped_symbols": skipped_symbols,
        "n_symbols_positive": n_symbols_positive,
        "min_positive_required": min_positive_required,
        "per_symbol_ok": per_symbol_ok,
        "passes_gate": passes,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "l1_gate_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Report saved to %s", report_path)

    combined_path = output_dir / "l1_gate_losses.csv"
    combined.to_csv(combined_path, index=False)
    logger.info("Losses saved to %s", combined_path)

    print()
    print("=" * 60)
    print("L1 GATE VALIDATION REPORT")
    print("=" * 60)
    print(dm_result)
    print(f"Mean loss diff (model - baseline): {report['mean_d']:.4f}")
    print(f"Total origins: {report['n_origins']}")
    if report.get("by_symbol"):
        print("Per-symbol breakdown:")
        for sym, m in report["by_symbol"].items():
            print(f"  {sym}: n={m['n_origins']}, mean_d={m['mean_d']:.4f}")
    if report.get("skipped_symbols"):
        print("Skipped symbols:")
        for sym, reason in report["skipped_symbols"].items():
            print(f"  {sym}: {reason}")
    print()
    if report.get("per_symbol_ok") is False:
        print(
            f"⚠️ Per-symbol sanity failed: only {report['n_symbols_positive']} symbols "
            f"with mean(d)<0 (need at least {report['min_positive_required']})"
        )
    if report["passes_gate"]:
        print("✅ L1 passes gate: significantly better than no-change baseline")
    else:
        print("⚠️ L1 does not pass gate")
    print("=" * 60)

    return 0 if report["passes_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
