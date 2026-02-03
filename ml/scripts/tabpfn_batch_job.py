#!/usr/bin/env python3
"""
Batch processing for multiple symbols (Docker entry point).

Environment variables:
    SYMBOLS: Comma-separated list (default: TSLA,NVDA,AAPL)
    PARALLEL: Run in parallel (default: true)
    MAX_WORKERS: Number of parallel workers (default: 2)
"""

import os
import sys
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _run_one_symbol(
    symbol: str,
    initial_train_days: int,
    test_days: int,
    step_days: int,
    use_tabpfn: bool,
) -> dict:
    """Run walk-forward for one symbol (picklable for ProcessPoolExecutor)."""
    from src.evaluation.walk_forward import walk_forward_validate

    try:
        result = walk_forward_validate(
            symbol=symbol,
            timeframe="d1",
            horizon_days=1,
            initial_train_days=initial_train_days,
            test_days=test_days,
            step_days=step_days,
            use_tabpfn=use_tabpfn,
        )
        return {
            "symbol": symbol,
            "success": True,
            "mean_accuracy": result["mean_accuracy"],
            "std_accuracy": result["std_accuracy"],
        }
    except Exception as e:
        logger.exception("%s: %s", symbol, e)
        return {"symbol": symbol, "success": False, "error": str(e)}


def main() -> None:
    symbols_str = os.getenv("SYMBOLS", "TSLA,NVDA,AAPL")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    parallel = os.getenv("PARALLEL", "true").lower() == "true"
    max_workers = int(os.getenv("MAX_WORKERS", "2"))
    initial_train_days = int(os.getenv("INITIAL_TRAIN_DAYS", "300"))
    test_days = int(os.getenv("TEST_DAYS", "50"))
    step_days = int(os.getenv("STEP_DAYS", "50"))
    use_tabpfn = os.getenv("USE_TABPFN", "true").lower() == "true"

    logger.info("Processing %s symbols: %s", len(symbols), ", ".join(symbols))
    logger.info(
        "Parallel: %s, Workers: %s",
        parallel,
        max_workers if parallel and len(symbols) > 1 else 1,
    )

    kwargs = {
        "initial_train_days": initial_train_days,
        "test_days": test_days,
        "step_days": step_days,
        "use_tabpfn": use_tabpfn,
    }

    results = []
    if parallel and len(symbols) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_one_symbol, sym, **kwargs): sym
                for sym in symbols
            }
            for future in as_completed(futures):
                results.append(future.result())
    else:
        for symbol in symbols:
            results.append(_run_one_symbol(symbol, **kwargs))

    logger.info("=" * 60)
    logger.info("BATCH RESULTS SUMMARY")
    logger.info("=" * 60)
    for r in results:
        if r.get("success"):
            logger.info(
                "%s: %.1f%% +/- %.1f%%",
                r["symbol"],
                r["mean_accuracy"] * 100,
                r["std_accuracy"] * 100,
            )
        else:
            logger.info("%s: FAILED - %s", r["symbol"], r.get("error", "Unknown"))
    successful = [r for r in results if r.get("success")]
    if successful:
        mean_acc = sum(r["mean_accuracy"] for r in successful) / len(successful)
        logger.info(
            "Overall mean: %.1f%% (%s/%s succeeded)",
            mean_acc * 100,
            len(successful),
            len(results),
        )
    logger.info("=" * 60)

    sys.exit(0 if all(r.get("success") for r in results) else 1)


if __name__ == "__main__":
    main()
