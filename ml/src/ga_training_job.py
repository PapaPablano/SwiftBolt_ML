"""GA Training Job - Collects and prepares data for genetic algorithm optimization.

This job:
1. Collects options ranking snapshots with price history
2. Stores them for GA backtesting
3. Runs GA optimization when enough data is available
4. Saves optimized parameters to database

Run modes:
    --collect: Collect ranking snapshot for GA training
    --optimize: Run GA optimization if sufficient data exists
    --symbol AAPL: Process specific symbol
    --all: Process all watchlist symbols
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.options_strategy_ga import (  # noqa: E402
    OptionsStrategyGA,
    fetch_training_data,
    save_ga_parameters,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Minimum data requirements
MIN_TRAINING_DAYS = 14
MIN_TRAINING_SAMPLES = 200
OPTIMAL_TRAINING_DAYS = 30


def collect_ranking_snapshot(symbol: str) -> int:
    """
    Collect current ranking snapshot for GA training.

    The options_ranks table already stores the data we need.
    This function ensures we have price context for backtesting.

    Returns:
        Number of records processed
    """
    logger.info(f"Collecting ranking snapshot for {symbol}")

    try:
        symbol_id = db.get_symbol_id(symbol)

        # Get latest rankings
        result = (
            db.client.table("options_ranks")
            .select(
                "contract_symbol, composite_rank, momentum_score, value_score, greeks_score, "
                "signal_buy, signal_discount, signal_runner, signal_greeks, "
                "mark, last_price, delta, gamma, theta, vega, iv_rank, run_at"
            )
            .eq("underlying_symbol_id", symbol_id)
            .order("run_at", desc=True)
            .limit(500)
            .execute()
        )

        if result.data:
            logger.info(f"Found {len(result.data)} ranking records for {symbol}")
            return len(result.data)

        logger.warning(f"No ranking data found for {symbol}")
        return 0

    except Exception as e:
        logger.error(f"Error collecting snapshot for {symbol}: {e}")
        return 0


def check_data_sufficiency(symbol: str) -> tuple[bool, int, int]:
    """
    Check if we have enough data for GA optimization.

    Returns:
        (is_sufficient, days_of_data, sample_count)
    """
    try:
        # Count distinct run dates
        result = db.client.rpc("count_ranking_data", {"p_symbol": symbol}).execute()

        if result.data:
            days = result.data[0].get("days", 0)
            samples = result.data[0].get("samples", 0)
            is_sufficient = days >= MIN_TRAINING_DAYS and samples >= MIN_TRAINING_SAMPLES
            return is_sufficient, days, samples

    except Exception as e:
        logger.warning(f"Error checking data sufficiency: {e}")

        # Fall back to direct query
        start_date = (datetime.utcnow() - timedelta(days=60)).isoformat()
        symbol_id = db.get_symbol_id(symbol)

        result = (
            db.client.table("options_ranks")
            .select("run_at", count="exact")
            .eq("underlying_symbol_id", symbol_id)
            .gte("run_at", start_date)
            .execute()
        )

        samples = result.count or 0
        days = min(60, samples // 50)  # Rough estimate

        is_sufficient = days >= MIN_TRAINING_DAYS and samples >= MIN_TRAINING_SAMPLES
        return is_sufficient, days, samples

    return False, 0, 0


def run_ga_optimization(
    symbol: str,
    generations: int = 50,
    population_size: int = 100,
    training_days: int = OPTIMAL_TRAINING_DAYS,
) -> Optional[dict]:
    """
    Run GA optimization for a symbol.

    Args:
        symbol: Underlying symbol
        generations: Number of GA generations
        population_size: Population size for GA
        training_days: Days of historical data to use

    Returns:
        Results dictionary or None if failed
    """
    logger.info(f"Starting GA optimization for {symbol}")
    logger.info(f"  Generations: {generations}")
    logger.info(f"  Population: {population_size}")
    logger.info(f"  Training days: {training_days}")

    # Create optimization run record
    run_id = None
    try:
        run_result = (
            db.client.table("ga_optimization_runs")
            .insert(
                {
                    "symbol": symbol,
                    "generations": generations,
                    "population_size": population_size,
                    "training_days": training_days,
                    "status": "running",
                }
            )
            .execute()
        )

        if run_result.data:
            run_id = run_result.data[0]["id"]
            logger.info(f"Created optimization run: {run_id}")
    except Exception as e:
        logger.warning(f"Failed to create run record: {e}")

    # Fetch training data
    training_data = fetch_training_data(symbol, days=training_days)

    if training_data.empty:
        logger.error(f"No training data found for {symbol}")
        _update_run_status(run_id, "failed", "No training data")
        return None

    logger.info(f"Loaded {len(training_data)} training samples")

    # Split for validation
    split_idx = int(len(training_data) * 0.8)
    train_df = training_data.iloc[:split_idx]
    valid_df = training_data.iloc[split_idx:]

    logger.info(f"Training: {len(train_df)} samples, Validation: {len(valid_df)} samples")

    # Run GA
    try:
        ga = OptionsStrategyGA(
            population_size=population_size,
            generations=generations,
            elite_fraction=0.10,
            mutation_rate=0.15,
        )

        results = ga.evolve(train_df, valid_df, verbose=True)

        if results.get("best_strategies"):
            best = results["best_strategies"][0]
            fitness = best.fitness

            logger.info("=" * 60)
            logger.info("GA OPTIMIZATION COMPLETE")
            logger.info("=" * 60)
            logger.info("Best Strategy:")
            logger.info(f"  Win Rate: {fitness.win_rate:.1%}")
            logger.info(f"  Profit Factor: {fitness.profit_factor:.2f}")
            logger.info(f"  Sharpe Ratio: {fitness.sharpe_ratio:.2f}")
            logger.info(f"  Max Drawdown: {fitness.max_drawdown:.1%}")
            logger.info(f"  Total Trades: {fitness.num_trades}")

            # Save to database
            save_ga_parameters(symbol, best.genes, fitness)

            # Update run status
            _update_run_status(
                run_id,
                "completed",
                best_fitness=fitness.score(),
                best_win_rate=fitness.win_rate,
                best_profit_factor=fitness.profit_factor,
                best_sharpe=fitness.sharpe_ratio,
                top_strategies=results.get("best_genes", [])[:5],
            )

            # Save sample trades for analysis
            _save_sample_trades(run_id, best)

            # Save to files
            ga.save_results(f"ga_results/{symbol}")

            return results

        else:
            logger.error("GA returned no strategies")
            _update_run_status(run_id, "failed", "No strategies generated")
            return None

    except Exception as e:
        logger.error(f"GA optimization failed: {e}", exc_info=True)
        _update_run_status(run_id, "failed", str(e))
        return None


def _update_run_status(run_id: Optional[str], status: str, error_message: str = None, **kwargs):
    """Update GA optimization run status."""
    if not run_id:
        return

    try:
        update_data = {"status": status, "completed_at": datetime.utcnow().isoformat()}

        if error_message:
            update_data["error_message"] = error_message

        for key, value in kwargs.items():
            if value is not None:
                # Convert snake_case to database column names
                db_key = key  # Already snake_case
                if isinstance(value, list):
                    import json

                    update_data[db_key] = json.dumps(value)
                else:
                    update_data[db_key] = value

        db.client.table("ga_optimization_runs").update(update_data).eq("id", run_id).execute()

    except Exception as e:
        logger.warning(f"Failed to update run status: {e}")


def _save_sample_trades(run_id: Optional[str], strategy) -> None:
    """Save sample trades from best strategy for analysis."""
    if not run_id or not strategy.trades:
        return

    try:
        sample_trades = strategy.trades[:50]  # First 50 trades

        for i, trade in enumerate(sample_trades):
            db.client.table("ga_backtest_trades").insert(
                {
                    "run_id": run_id,
                    "strategy_rank": 1,
                    "symbol": trade.symbol,
                    "contract_symbol": trade.contract_symbol,
                    "entry_date": trade.entry_date,
                    "exit_date": trade.exit_date,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "delta_entry": trade.delta_entry,
                    "gamma_entry": trade.gamma_entry,
                    "vega_entry": trade.vega_entry,
                    "theta_entry": trade.theta_entry,
                    "pnl_pct": trade.pnl_pct,
                    "duration_minutes": trade.duration_minutes,
                    "exit_reason": trade.exit_reason,
                    "entry_signal": trade.entry_signal,
                }
            ).execute()

        logger.info(f"Saved {len(sample_trades)} sample trades")

    except Exception as e:
        logger.warning(f"Failed to save sample trades: {e}")


def get_watchlist_symbols() -> list[str]:
    """Get symbols from active watchlists."""
    try:
        result = db.client.table("watchlist_items").select("symbol_id(ticker)").execute()

        if result.data:
            symbols = set()
            for item in result.data:
                if item.get("symbol_id") and item["symbol_id"].get("ticker"):
                    symbols.add(item["symbol_id"]["ticker"])
            return list(symbols)

    except Exception as e:
        logger.warning(f"Failed to get watchlist symbols: {e}")

    # Fall back to settings
    return settings.symbols_to_process


def main():
    parser = argparse.ArgumentParser(
        description="GA Training Job - Collect data and optimize strategies"
    )
    parser.add_argument(
        "--collect", action="store_true", help="Collect ranking snapshot for training"
    )
    parser.add_argument("--optimize", action="store_true", help="Run GA optimization")
    parser.add_argument("--symbol", type=str, help="Single symbol to process")
    parser.add_argument("--all", action="store_true", help="Process all watchlist symbols")
    parser.add_argument("--generations", type=int, default=50, help="Number of GA generations")
    parser.add_argument(
        "--days", type=int, default=OPTIMAL_TRAINING_DAYS, help="Training data days"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force optimization even if data is insufficient"
    )

    args = parser.parse_args()

    # Determine symbols to process
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.all:
        symbols = get_watchlist_symbols()
    else:
        symbols = settings.symbols_to_process

    logger.info("=" * 60)
    logger.info("GA Training Job")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Mode: {'collect' if args.collect else 'optimize' if args.optimize else 'auto'}")
    logger.info("=" * 60)

    results = {"collected": 0, "optimized": 0, "skipped": 0, "failed": 0}

    for symbol in symbols:
        logger.info(f"\n{'='*40}")
        logger.info(f"Processing {symbol}")
        logger.info("=" * 40)

        # Collect mode
        if args.collect:
            count = collect_ranking_snapshot(symbol)
            if count > 0:
                results["collected"] += 1
            continue

        # Check data sufficiency
        is_sufficient, days, samples = check_data_sufficiency(symbol)

        logger.info(f"Data: {days} days, {samples} samples")
        logger.info(f"Sufficient: {is_sufficient}")

        # Optimize mode
        if args.optimize or (not args.collect):
            if is_sufficient or args.force:
                result = run_ga_optimization(
                    symbol, generations=args.generations, training_days=args.days
                )
                if result:
                    results["optimized"] += 1
                else:
                    results["failed"] += 1
            else:
                logger.info(f"Skipping {symbol} - insufficient data")
                logger.info(f"  Need: {MIN_TRAINING_DAYS} days, {MIN_TRAINING_SAMPLES} samples")
                logger.info(f"  Have: {days} days, {samples} samples")
                results["skipped"] += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("GA Training Job Complete")
    logger.info("=" * 60)
    logger.info(f"Collected: {results['collected']}")
    logger.info(f"Optimized: {results['optimized']}")
    logger.info(f"Skipped: {results['skipped']}")
    logger.info(f"Failed: {results['failed']}")


if __name__ == "__main__":
    main()
