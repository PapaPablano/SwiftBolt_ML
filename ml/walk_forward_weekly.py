#!/usr/bin/env python3
"""Walk-forward validation for weekly predictions with enhanced analytics."""

import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from walk_forward_compare import walk_forward_validation

try:
    from src.data.data_cleaner import DataCleaner
    USE_CLEANER = True
except ImportError:
    USE_CLEANER = False


def calculate_historical_stats(df: pd.DataFrame, horizon_days: int, threshold_pct: float):
    """Calculate actual historical move statistics."""
    returns = df['close'].pct_change(periods=horizon_days).shift(-horizon_days)
    
    # Calculate stats
    all_moves = returns.abs()
    significant_moves = returns[abs(returns) > threshold_pct]
    
    stats = {
        'avg_all_moves': all_moves.mean(),
        'avg_significant_moves': significant_moves.abs().mean() if len(significant_moves) > 0 else threshold_pct * 1.5,
        'pct_significant': len(significant_moves) / len(returns.dropna()) if len(returns.dropna()) > 0 else 0.5,
        'median_significant': significant_moves.abs().median() if len(significant_moves) > 0 else threshold_pct * 1.2,
        'std_significant': significant_moves.abs().std() if len(significant_moves) > 0 else threshold_pct * 0.5,
    }
    
    return stats


def walk_forward_weekly(
    model_class,
    df: pd.DataFrame,
    sentiment: pd.Series | None,
    threshold_pct: float,
    horizon_days: int,
    train_window: int = 252,
    refit_frequency: int = 21,
):
    """Walk-forward with custom horizon."""

    class HorizonForecaster(model_class):
        def prepare_training_data_binary(self, df_inner, **kwargs):
            kwargs["horizon_days"] = horizon_days
            return super().prepare_training_data_binary(df_inner, **kwargs)

    return walk_forward_validation(
        HorizonForecaster,
        df,
        sentiment,
        threshold_pct=threshold_pct,
        train_window=train_window,
        refit_frequency=refit_frequency,
    )


def calculate_expected_returns(accuracy: float, horizon_days: int, threshold_pct: float, 
                               avg_move: float, portfolio_size: float = 100000):
    """Calculate detailed expected returns with realistic costs."""
    
    # Edge calculation
    edge = (accuracy - 0.5) * 2
    
    # Trading frequency
    trades_per_year = int(252 / horizon_days)
    
    # Cost model (realistic for 2026)
    commission_per_trade = 0  # Most brokers are $0 commission
    slippage_pct = 0.0003  # 0.03% average slippage on market orders
    spread_pct = 0.0002    # 0.02% bid-ask spread
    cost_per_trade_pct = (slippage_pct + spread_pct) * 2  # Round trip
    
    # Per-trade expectation
    win_rate = accuracy
    avg_win = avg_move
    avg_loss = avg_move  # Assume symmetric losses
    expected_per_trade = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Annual returns
    gross_return_pct = expected_per_trade * trades_per_year
    total_costs_pct = trades_per_year * cost_per_trade_pct
    net_return_pct = gross_return_pct - total_costs_pct
    
    # Dollar amounts
    gross_return_dollars = portfolio_size * gross_return_pct
    total_costs_dollars = portfolio_size * total_costs_pct
    net_return_dollars = portfolio_size * net_return_pct
    
    return {
        'accuracy': accuracy,
        'edge': edge,
        'trades_per_year': trades_per_year,
        'avg_move': avg_move,
        'expected_per_trade': expected_per_trade,
        'gross_return_pct': gross_return_pct,
        'total_costs_pct': total_costs_pct,
        'cost_per_trade_pct': cost_per_trade_pct,
        'net_return_pct': net_return_pct,
        'gross_return_dollars': gross_return_dollars,
        'total_costs_dollars': total_costs_dollars,
        'net_return_dollars': net_return_dollars,
    }


def print_performance_summary(model_name: str, metrics: dict, portfolio_size: float = 100000):
    """Print detailed performance summary."""
    
    print(f"\n✅ PRODUCTION READY: {model_name} ({metrics['accuracy']:.1%})")
    print(f"\n{'='*60}")
    print("📊 EXPECTED ANNUAL PERFORMANCE")
    print(f"{'='*60}")
    
    print(f"\n📈 Trading Metrics:")
    print(f"  Accuracy:              {metrics['accuracy']:.1%}")
    print(f"  Edge over random:      {metrics['edge']:.1%}")
    print(f"  Trades per year:       {metrics['trades_per_year']}")
    print(f"  Avg move (threshold+): {metrics['avg_move']:.2%}")
    print(f"  Expected per trade:    {metrics['expected_per_trade']:.2%}")
    
    print(f"\n💰 Return Projections:")
    print(f"  Gross return:          {metrics['gross_return_pct']:.1%}")
    print(f"  Transaction costs:     {metrics['total_costs_pct']:.2%} ({metrics['cost_per_trade_pct']:.3%} per trade)")
    print(f"  NET RETURN:            {metrics['net_return_pct']:.1%} 🔥")
    
    print(f"\n💵 Dollar Projections (${portfolio_size:,.0f} portfolio):")
    print(f"  Gross profit:          ${metrics['gross_return_dollars']:,.0f}")
    print(f"  Total costs:           ${metrics['total_costs_dollars']:,.0f}")
    print(f"  NET PROFIT:            ${metrics['net_return_dollars']:,.0f} 🔥")
    
    # Risk-adjusted metrics
    sharpe_estimate = metrics['net_return_pct'] / (metrics['avg_move'] * np.sqrt(metrics['trades_per_year']))
    print(f"\n📊 Risk Metrics (estimated):")
    print(f"  Estimated Sharpe:      {sharpe_estimate:.2f}")
    print(f"  Max expected drawdown: {metrics['avg_move'] * 3:.1%} (3x avg move)")
    
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Walk-forward validation for weekly predictions")
    parser.add_argument("symbol", nargs="?", default="TSLA", help="Stock symbol (default: TSLA)")
    parser.add_argument("--timeframe", choices=["d1", "h4"], default="d1",
                        help="Bar timeframe: d1=daily, h4=4h (use h4 for 1000+ samples for TabPFN)")
    parser.add_argument("--horizon", type=int, default=None,
                        help="Horizon in bars (default: 5 for d1, 24 for h4 ~4 days)")
    parser.add_argument("--threshold", type=float, default=0.02, help="Threshold %% (default: 2%%)")
    parser.add_argument("--portfolio", type=float, default=100000, help="Portfolio size (default: $100k)")
    parser.add_argument("--train-window", type=int, default=None,
                        help="Training window in bars (default: 252 d1, 1008 h4)")
    parser.add_argument("--refit-freq", type=int, default=None,
                        help="Refit frequency in bars (default: 21 d1, 42 h4)")
    parser.add_argument("--kaggle", action="store_true", help="Use Kaggle price-volume dataset (borismarjanovic) instead of Supabase")
    parser.add_argument("--no-sentiment", action="store_true", help="Skip sentiment features (Supabase only)")
    parser.add_argument("--no-hybrid", action="store_true", help="Skip TabPFN+XGBoost hybrid model")
    parser.add_argument("--h4-source", choices=["supabase", "alpaca_clone"], default="supabase",
                        help="When timeframe=h4: supabase=ohlc_bars_v2, alpaca_clone=ohlc_bars_h4_alpaca (TabPFN experiments)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    timeframe = args.timeframe
    # Defaults by timeframe: d1 = daily (ohlc_bars_v2), h4 = 4h (ohlc_bars_h4_alpaca when h4_source=alpaca_clone)
    if args.horizon is not None:
        horizon = args.horizon
    else:
        # h4: 24 bars = 4 days; d1: 5 bars = 5 days
        horizon = 24 if timeframe == "h4" else 5
    if args.train_window is not None:
        train_window = args.train_window
    else:
        # h4: 1008 bars = 6 weeks (7*24/4); d1: 252 trading days
        train_window = 1008 if timeframe == "h4" else 252
    if args.refit_freq is not None:
        refit_freq = args.refit_freq
    else:
        # h4: refit every 42 bars (~1 week); d1: every 21 days
        refit_freq = 42 if timeframe == "h4" else 21
    threshold = args.threshold
    portfolio_size = args.portfolio
    # For expected-returns: horizon in "effective days" (h4: ~6 bars/day)
    effective_days = horizon if timeframe == "d1" else max(1, horizon // 6)
    # 4h bars only from Supabase (Kaggle is daily)
    use_kaggle = args.kaggle and timeframe != "h4"

    print(f"\n{'='*60}")
    print(f"WALK-FORWARD VALIDATION: {symbol}")
    print(f"{'='*60}")
    print(f"Timeframe:      {timeframe} ({'4h bars' if timeframe == 'h4' else 'daily'})")
    print(f"Horizon:        {horizon} bars" + (" (~4 days)" if timeframe == "h4" and horizon == 24 else ""))
    print(f"Threshold:      {threshold:.1%}")
    print(f"Train window:   {train_window} bars")
    print(f"Refit freq:     {refit_freq} bars")
    print(f"Portfolio size: ${portfolio_size:,.0f}")
    h4_source = getattr(args, "h4_source", "supabase")
    data_source_label = "Kaggle (price-volume)" if use_kaggle else (
        "Supabase (Alpaca 4h clone)" if (timeframe == "h4" and h4_source == "alpaca_clone") else "Supabase"
    )
    print(f"Data source:    {data_source_label}")
    if getattr(args, "no_sentiment", False) and not use_kaggle:
        print("Sentiment:      skipped (--no-sentiment)")
    print(f"{'='*60}\n")

    # Fetch limit and min bars: h4 for 1000+ samples (TabPFN), d1 for ~600
    fetch_limit = 1200 if timeframe == "h4" else 600
    # h4: require 400+ bars so job runs (800+ ideal for TabPFN; Supabase may have fewer 4h bars)
    min_bars = 400 if timeframe == "h4" else 300
    if args.kaggle and timeframe == "h4":
        print("⚠️ Kaggle has daily data only; using Supabase for h4.")

    print(f"Loading {symbol} data ({timeframe})...")
    if use_kaggle:
        try:
            from src.data.kaggle_stock_data import get_kaggle_path, load_symbol_ohlcv
            kaggle_path = get_kaggle_path()
            df = load_symbol_ohlcv(symbol, path=kaggle_path, limit=fetch_limit)
        except Exception as e:
            print(f"❌ Kaggle data error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        print("✅ Using Kaggle price-volume dataset (no sentiment)")
    else:
        try:
            from src.data.supabase_db import SupabaseDatabase
            db = SupabaseDatabase()
            source = "alpaca_4h" if (timeframe == "h4" and getattr(args, "h4_source", "supabase") == "alpaca_clone") else None
            df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=fetch_limit, source=source)
            if USE_CLEANER and df is not None and len(df) > 0:
                print("Cleaning data (DataCleaner)...")
                df = DataCleaner.clean_all(df, verbose=False)
        except Exception as e:
            print(f"❌ Database error: {e}")
            sys.exit(1)

    if df is None or len(df) < min_bars:
        print(f"❌ Insufficient data (need {min_bars}+ bars for {timeframe})")
        sys.exit(1)

    print(f"✅ Loaded {len(df)} bars")
    if timeframe == "h4" and len(df) < 800:
        print(f"⚠️ Fewer than 800 4h bars; TabPFN will use available data (1000+ ideal for full ensemble).")

    # walk_forward_validation requires len(X) >= train_window + 50.
    # prepare_training_data_binary yields len(X) <= len(df) - 50 - horizon (start_idx=50, end_idx=len(df)-horizon).
    # So we need train_window + 50 <= len(df) - 50 - horizon - buffer => train_window <= len(df) - 110 - horizon.
    min_required = train_window + 50
    max_X_rows = max(0, len(df) - 50 - horizon)  # baseline_forecaster drop: 50 + horizon
    train_window_cap = max(100, len(df) - 110 - horizon)  # buffer 10 for filtered small-move rows
    if train_window > train_window_cap or max_X_rows < min_required:
        old_tw, old_rf = train_window, refit_freq
        train_window = min(train_window, train_window_cap, max(100, max_X_rows - 50))  # ensure train_window+50 <= max_X_rows
        refit_freq = min(refit_freq, max(21, train_window // 5))
        if train_window < old_tw or refit_freq < old_rf:
            print(f"⚠️ Capped train_window to {train_window} and refit_freq to {refit_freq} (have {len(df)} bars, max ~{max_X_rows} usable after feature prep).")
    if max_X_rows < train_window + 50:
        print(f"❌ Insufficient data for walk-forward: max ~{max_X_rows} usable rows after feature prep, need {train_window + 50}+.")
        sys.exit(1)

    # Calculate historical statistics
    print(f"\nCalculating historical statistics...")
    hist_stats = calculate_historical_stats(df, horizon, threshold)
    print(f"✅ Historical Stats:")
    print(f"  Avg all moves:         {hist_stats['avg_all_moves']:.2%}")
    print(f"  Avg significant moves: {hist_stats['avg_significant_moves']:.2%}")
    print(f"  % significant:         {hist_stats['pct_significant']:.1%}")
    print(f"  Median significant:    {hist_stats['median_significant']:.2%}")
    print(f"  Std significant:       {hist_stats['std_significant']:.2%}")

    # Load sentiment (skip when using Kaggle data or --no-sentiment)
    sentiment = None
    if not use_kaggle and not getattr(args, "no_sentiment", False):
        start_date = pd.to_datetime(df["ts"]).min().date()
        end_date = pd.to_datetime(df["ts"]).max().date()
        try:
            print(f"\nLoading sentiment data...")
            from src.features.stock_sentiment import get_historical_sentiment_series
            sentiment = get_historical_sentiment_series(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                use_finviz_realtime=True,
            )
            if sentiment is not None and len(sentiment) > 0:
                print(f"✅ Loaded {len(sentiment)} sentiment records")
            else:
                print(f"⚠️ No sentiment data available")
        except Exception as e:
            print(f"⚠️ Sentiment loading failed: {e}")
    elif getattr(args, "no_sentiment", False) and not use_kaggle:
        print("⚠️ Skipping sentiment (--no-sentiment)")

    results = {}

    # Test XGBoost
    print("\n" + "="*60)
    print(f"XGBoost Walk-Forward: {symbol} ({horizon}-bar horizon)")
    print("="*60)
    try:
        from src.models.xgboost_forecaster import XGBoostForecaster
        results["XGBoost"] = walk_forward_weekly(
            XGBoostForecaster,
            df,
            sentiment,
            threshold_pct=threshold,
            horizon_days=horizon,
            train_window=train_window,
            refit_frequency=refit_freq,
        )
        print(f"✅ XGBoost completed: {results['XGBoost']['accuracy']:.1%} accuracy")
        # Write predictions CSV (timeframe in filename so 4h vs daily is clear)
        res = results["XGBoost"]
        if res.get("prediction_dates") and res.get("predictions") is not None and res.get("actuals") is not None:
            out_dir = Path(__file__).resolve().parent / "results"
            out_dir.mkdir(parents=True, exist_ok=True)
            csv_path = out_dir / f"{symbol}_walk_forward_predictions_{timeframe}.csv"
            pred_df = pd.DataFrame({
                "date": res["prediction_dates"],
                "actual": res["actuals"],
                "predicted": res["predictions"],
                "timeframe": timeframe,
            })
            pred_df.to_csv(csv_path, index=False)
            print(f"📄 Predictions saved: {csv_path}")
    except Exception as e:
        print(f"❌ XGBoost failed: {e}")
        import traceback
        traceback.print_exc()
        results["XGBoost"] = {"accuracy": 0.0, "n_windows": 0, "n_predictions": 0}

    # Test ARIMA-GARCH
    print("\n" + "="*60)
    print(f"ARIMA-GARCH Walk-Forward: {symbol} ({horizon}-bar horizon)")
    print("="*60)
    try:
        from src.models.arima_garch_forecaster import ARIMAGARCHForecaster
        results["ARIMA"] = walk_forward_weekly(
            ARIMAGARCHForecaster,
            df,
            sentiment,
            threshold_pct=threshold,
            horizon_days=horizon,
            train_window=train_window,
            refit_frequency=refit_freq,
        )
        print(f"✅ ARIMA-GARCH completed: {results['ARIMA']['accuracy']:.1%} accuracy")
    except Exception as e:
        print(f"❌ ARIMA-GARCH failed: {e}")
        import traceback
        traceback.print_exc()
        results["ARIMA"] = {"accuracy": 0.0, "n_windows": 0, "n_predictions": 0}

    # Hybrid TabPFN + XGBoost (optional)
    if not args.no_hybrid:
        print("\n" + "="*60)
        print(f"Hybrid (TabPFN+XGB) Walk-Forward: {symbol} ({horizon}-bar horizon)")
        print("="*60)
        try:
            from src.models.hybrid_tabpfn_xgb_forecaster import HybridTabPFN_XGBForecaster
            results["Hybrid"] = walk_forward_weekly(
                HybridTabPFN_XGBForecaster,
                df,
                sentiment,
                threshold_pct=threshold,
                horizon_days=horizon,
                train_window=train_window,
                refit_frequency=refit_freq,
            )
            print(f"✅ Hybrid completed: {results['Hybrid']['accuracy']:.1%} accuracy")
        except Exception as e:
            print(f"❌ Hybrid failed: {e}")
            import traceback
            traceback.print_exc()
            results["Hybrid"] = {"accuracy": 0.0, "n_windows": 0, "n_predictions": 0}

    # Print summary
    print("\n" + "="*60)
    print(f"WALK-FORWARD RESULTS: {symbol} ({horizon}D HORIZON)")
    print("="*60)
    for model, res in sorted(results.items(), key=lambda x: x[1]["accuracy"], reverse=True):
        print(f"{model:20s}: {res['accuracy']:.1%} ({res['n_windows']} windows, {res['n_predictions']} predictions)")
    print("="*60)

    best = max(results.items(), key=lambda x: x[1]["accuracy"])
    acc = best[1]["accuracy"]

    # Use actual historical average move
    avg_move = hist_stats['avg_significant_moves']

    if acc >= 0.70:
        metrics = calculate_expected_returns(
            accuracy=acc,
            horizon_days=effective_days,
            threshold_pct=threshold,
            avg_move=avg_move,
            portfolio_size=portfolio_size,
        )
        print_performance_summary(best[0], metrics, portfolio_size)
        
    elif acc >= 0.60:
        print(f"\n⚠️ MARGINAL PERFORMANCE: {best[0]} ({acc:.1%})")
        print("\nRecommendations:")
        print("  1. Try different horizon (test 3d, 5d, 10d, 21d)")
        print("  2. Add confidence filtering (only trade high-confidence predictions)")
        print("  3. Combine with other signals or filters")
        print("  4. Test on different symbols")
        
        metrics = calculate_expected_returns(
            accuracy=acc,
            horizon_days=effective_days,
            threshold_pct=threshold,
            avg_move=avg_move,
            portfolio_size=portfolio_size,
        )
        print(f"\n📊 Expected returns at {acc:.1%} accuracy:")
        print(f"  Net return: {metrics['net_return_pct']:.1%} (${metrics['net_return_dollars']:,.0f})")
        
    else:
        print(f"\n❌ BELOW 60% THRESHOLD: {best[0]} ({acc:.1%})")
        print("\nThis model is not production-ready. Try:")
        print("  1. Different horizon (test 5d, 10d, 21d)")
        print("  2. Different symbols (high volatility stocks work better)")
        print("  3. Add more features or different model architecture")
        print("  4. Check data quality and feature engineering")

    # Compare to baseline
    print(f"\n{'='*60}")
    print("📊 COMPARISON TO BASELINES")
    print(f"{'='*60}")
    print(f"Best model ({best[0]}):  {acc:.1%}")
    print(f"Random baseline:         50.0%")
    print(f"Lift over random:        {(acc - 0.5) * 100:.1f}pp")
    if len(results) > 1:
        worst = min(results.items(), key=lambda x: x[1]["accuracy"])
        print(f"Worst model ({worst[0]}): {worst[1]['accuracy']:.1%}")
        print(f"Model improvement:       {(acc - worst[1]['accuracy']) * 100:.1f}pp")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
