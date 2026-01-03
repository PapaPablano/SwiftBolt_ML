"""
Ranking Evaluation Job - Validates options ranking system health.

Equivalent to forecast_evaluations for the ranking system.
Runs periodically to:
1. Compute daily Rank IC
2. Check for IC degradation/collapse
3. Detect data leakage
4. Monitor hit rate anomalies
5. Store results to ranking_evaluations table
6. Generate alerts for critical issues

Usage:
    python ranking_evaluation_job.py --symbol AAPL --days 30
    python ranking_evaluation_job.py --all --days 60
"""

import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.models.ranking_monitor import RankingMonitor, AlertSeverity
from src.models.ranking_calibrator import IsotonicCalibrator

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_historical_rankings(
    symbol_id: str,
    days: int = 30,
    ranking_mode: str = "entry",
) -> pd.DataFrame:
    """Fetch historical rankings for a symbol."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        result = (
            db.client.table("options_ranks")
            .select(
                "contract_symbol,strike,side,expiry,composite_rank,"
                "momentum_score,value_score,greeks_score,run_at,"
                "signal_buy,signal_discount,signal_runner"
            )
            .eq("underlying_symbol_id", symbol_id)
            .eq("ranking_mode", ranking_mode)
            .gte("run_at", cutoff)
            .order("run_at", desc=True)
            .execute()
        )

        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)
        df["ranking_date"] = pd.to_datetime(df["run_at"]).dt.date
        return df

    except Exception as e:
        logger.error(f"Failed to fetch rankings: {e}")
        return pd.DataFrame()


def fetch_forward_returns(
    symbol_id: str,
    days: int = 30,
    horizon_days: int = 1,
) -> pd.DataFrame:
    """
    Fetch forward returns for ranked contracts.

    Joins options_ranks with options_history to compute actual returns.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        query = f"""
        WITH ranked AS (
            SELECT 
                contract_symbol,
                run_at::date as ranking_date,
                composite_rank,
                mark as entry_price
            FROM options_ranks
            WHERE underlying_symbol_id = '{symbol_id}'
              AND run_at >= '{cutoff}'
        ),
        future_prices AS (
            SELECT 
                contract_symbol,
                ts::date as price_date,
                mark as exit_price
            FROM options_history
            WHERE symbol_id = '{symbol_id}'
              AND ts >= '{cutoff}'
        )
        SELECT 
            r.contract_symbol,
            r.ranking_date,
            r.composite_rank,
            r.entry_price,
            f.exit_price,
            CASE 
                WHEN r.entry_price > 0 
                THEN (f.exit_price - r.entry_price) / r.entry_price
                ELSE 0 
            END as forward_return
        FROM ranked r
        LEFT JOIN future_prices f 
            ON r.contract_symbol = f.contract_symbol
            AND f.price_date = r.ranking_date + INTERVAL '{horizon_days} days'
        WHERE f.exit_price IS NOT NULL
        """

        result = db.client.rpc("execute_sql", {"query": query}).execute()

        if not result.data:
            return pd.DataFrame()

        return pd.DataFrame(result.data)

    except Exception as e:
        logger.warning(f"RPC failed, using fallback method: {e}")
        return _fetch_returns_fallback(symbol_id, days, horizon_days)


def _fetch_returns_fallback(
    symbol_id: str,
    days: int,
    horizon_days: int,
) -> pd.DataFrame:
    """Fallback method to compute returns without RPC."""
    rankings = fetch_historical_rankings(symbol_id, days)
    if rankings.empty:
        return pd.DataFrame()

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        history = (
            db.client.table("options_history")
            .select("contract_symbol,ts,mark")
            .eq("symbol_id", symbol_id)
            .gte("ts", cutoff)
            .execute()
        )

        if not history.data:
            return pd.DataFrame()

        hist_df = pd.DataFrame(history.data)
        hist_df["price_date"] = pd.to_datetime(hist_df["ts"]).dt.date

        returns_data = []
        for _, rank_row in rankings.iterrows():
            contract = rank_row["contract_symbol"]
            rank_date = rank_row["ranking_date"]
            target_date = rank_date + timedelta(days=horizon_days)

            entry = hist_df[
                (hist_df["contract_symbol"] == contract) &
                (hist_df["price_date"] == rank_date)
            ]
            exit_row = hist_df[
                (hist_df["contract_symbol"] == contract) &
                (hist_df["price_date"] == target_date)
            ]

            if not entry.empty and not exit_row.empty:
                entry_price = entry.iloc[0]["mark"]
                exit_price = exit_row.iloc[0]["mark"]

                if entry_price > 0:
                    forward_return = (exit_price - entry_price) / entry_price
                    returns_data.append({
                        "contract_symbol": contract,
                        "ranking_date": rank_date,
                        "composite_rank": rank_row["composite_rank"],
                        "forward_return": forward_return,
                    })

        return pd.DataFrame(returns_data)

    except Exception as e:
        logger.error(f"Fallback return calculation failed: {e}")
        return pd.DataFrame()


def store_evaluation(
    symbol_id: str,
    report,
    horizon: str = "1D",
    ranking_mode: str = "entry",
) -> None:
    """Store evaluation results to database."""
    try:
        has_critical = any(
            a.severity == AlertSeverity.CRITICAL for a in report.alerts
        )

        record = {
            "symbol_id": symbol_id,
            "evaluated_at": report.timestamp.isoformat(),
            "is_healthy": report.is_healthy,
            "n_days": report.n_days_evaluated,
            "n_contracts": report.n_contracts_evaluated,
            "mean_ic": report.metrics.get("mean_ic"),
            "std_ic": report.metrics.get("std_ic"),
            "min_ic": report.metrics.get("min_ic"),
            "max_ic": report.metrics.get("max_ic"),
            "ic_trend": report.metrics.get("recent_ic_trend"),
            "stability": report.metrics.get("stability"),
            "hit_rate": report.metrics.get("hit_rate"),
            "hit_rate_n": report.metrics.get("hit_rate_n"),
            "hit_rate_ci_lower": report.metrics.get("hit_rate_ci_lower"),
            "hit_rate_ci_upper": report.metrics.get("hit_rate_ci_upper"),
            "leakage_suspected": report.metrics.get("leakage_suspected", False),
            "leakage_score": report.metrics.get("leakage_score"),
            "permuted_ic_mean": report.metrics.get("permuted_ic_mean"),
            "n_alerts": len(report.alerts),
            "alert_types": [a.alert_type.value for a in report.alerts],
            "has_critical_alert": has_critical,
            "horizon": horizon,
            "ranking_mode": ranking_mode,
        }

        db.client.table("ranking_evaluations").insert(record).execute()
        logger.info(f"Stored evaluation for {symbol_id}")

    except Exception as e:
        logger.error(f"Failed to store evaluation: {e}")


def fit_and_save_calibrator(
    symbol: str,
    symbol_id: str,
    days: int = 60,
) -> None:
    """Fit calibrator on historical data and save."""
    logger.info(f"Fitting calibrator for {symbol}...")

    rankings = fetch_historical_rankings(symbol_id, days)
    returns = fetch_forward_returns(symbol_id, days)

    if rankings.empty or returns.empty:
        logger.warning(f"Insufficient data to fit calibrator for {symbol}")
        return

    merged = rankings.merge(
        returns[["contract_symbol", "ranking_date", "forward_return"]],
        on=["contract_symbol", "ranking_date"],
        how="inner"
    )

    if len(merged) < 100:
        logger.warning(
            f"Only {len(merged)} samples for calibration, need at least 100"
        )
        return

    calibrator = IsotonicCalibrator()
    result = calibrator.fit(
        merged["composite_rank"].values,
        merged["forward_return"].values,
    )

    logger.info(f"Calibration result: {result}")

    calibrator_dir = Path(__file__).parent / "calibrators"
    calibrator_dir.mkdir(exist_ok=True)

    calibrator_path = calibrator_dir / f"{symbol}_cal.json"
    calibrator.save(str(calibrator_path))
    logger.info(f"Saved calibrator to {calibrator_path}")


def evaluate_symbol(
    symbol: str,
    days: int = 30,
    horizon_days: int = 1,
    ranking_mode: str = "entry",
    fit_calibrator: bool = False,
) -> None:
    """Run full evaluation for a symbol."""
    logger.info(f"Evaluating ranking health for {symbol}...")

    symbol_id = db.get_symbol_id(symbol)

    rankings = fetch_historical_rankings(symbol_id, days, ranking_mode)
    returns = fetch_forward_returns(symbol_id, days, horizon_days)

    if rankings.empty:
        logger.warning(f"No rankings found for {symbol}")
        return

    if returns.empty:
        logger.warning(f"No forward returns found for {symbol}")
        return

    merged = rankings.merge(
        returns[["contract_symbol", "ranking_date", "forward_return"]],
        on=["contract_symbol", "ranking_date"],
        how="inner"
    )

    logger.info(
        f"Merged {len(merged)} samples from {len(rankings)} rankings"
    )

    monitor = RankingMonitor(lookback_days=days)
    report = monitor.evaluate(
        merged,
        merged,
        date_col="ranking_date",
        score_col="composite_rank",
        return_col="forward_return",
        contract_col="contract_symbol",
    )

    print(report)

    for alert in report.alerts:
        if alert.severity == AlertSeverity.CRITICAL:
            logger.error(str(alert))
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(str(alert))

    horizon = f"{horizon_days}D"
    store_evaluation(symbol_id, report, horizon, ranking_mode)

    if fit_calibrator:
        fit_and_save_calibrator(symbol, symbol_id, days)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate options ranking system health"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Symbol to evaluate (e.g., AAPL)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all symbols from settings",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of history to evaluate (default: 30)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=1,
        help="Forward return horizon in days (default: 1)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="entry",
        choices=["entry", "exit"],
        help="Ranking mode to evaluate",
    )
    parser.add_argument(
        "--fit-calibrator",
        action="store_true",
        help="Fit and save calibrator after evaluation",
    )

    args = parser.parse_args()

    if args.all:
        symbols = settings.symbols_to_process
    elif args.symbol:
        symbols = [args.symbol.upper()]
    else:
        parser.error("Must specify --symbol or --all")
        return

    logger.info("=" * 60)
    logger.info("RANKING EVALUATION JOB")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Days: {args.days}, Horizon: {args.horizon}D")
    logger.info("=" * 60)

    for symbol in symbols:
        try:
            evaluate_symbol(
                symbol,
                days=args.days,
                horizon_days=args.horizon,
                ranking_mode=args.mode,
                fit_calibrator=args.fit_calibrator,
            )
        except Exception as e:
            logger.error(f"Failed to evaluate {symbol}: {e}")

    logger.info("=" * 60)
    logger.info("RANKING EVALUATION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
