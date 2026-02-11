"""
Run a single experiment: load config → data → model → evaluate → save results.

No production deps. Results written to forecasting_lab/results/ (local only).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Allow running as python -m forecasting_lab.runner.run_experiment from ml/
LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from forecasting_lab.data.base import DataAdapter
from forecasting_lab.evaluation.forecast_eval import (
    aggregate_forecast_eval,
    forecast_eval_from_fold,
    residual_features_from_fold,
)
from forecasting_lab.evaluation.metrics import compute_metrics
from forecasting_lab.evaluation.walk_forward import walk_forward_splits
from forecasting_lab.models.base import BaseForecaster


def load_config(config_path: Path) -> dict:
    """Load YAML config."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_adapter(name: str) -> DataAdapter:
    """Resolve data adapter by name."""
    if name == "yfinance":
        from forecasting_lab.data.yfinance_adapter import YFinanceAdapter
        return YFinanceAdapter()
    if name == "csv":
        from forecasting_lab.data.csv_adapter import CSVAdapter
        return CSVAdapter()
    if name == "alpaca":
        from forecasting_lab.data.alpaca_adapter import AlpacaAdapter
        return AlpacaAdapter()
    raise ValueError(f"Unknown data adapter: {name}")


def _pred_closes(pred: list | np.ndarray, horizon: int) -> np.ndarray:
    """Extract close from predict output: list of OHLC dicts -> array of closes."""
    if hasattr(pred, "__len__") and len(pred) > 0 and isinstance(pred[0], dict):
        return np.array([float(p["close"]) for p in pred[:horizon]])
    return np.asarray(pred).ravel()[:horizon]


def run_one_fold(
    model: BaseForecaster,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    horizon: int,
    target_col: str,
    residual_last_k: int = 5,
    metrics_list: list[str] | None = None,
) -> tuple[list[float], dict, dict, dict]:
    """
    Train, predict (OHLC), compute metrics (config-driven), forecast_eval (y_prev anchored), residual features.
    Returns: (pred_closes, metrics, forecast_eval, residual_features).
    """
    model.train(df_train, target_col=target_col, horizon=horizon)
    pred = model.predict(df_train, horizon=horizon)
    pred_arr = _pred_closes(pred, horizon)
    y_test = df_test[target_col].values[: len(pred_arr)]
    if len(y_test) == 0:
        return list(pred_arr), {}, {}, {}
    metrics = compute_metrics(y_test, pred_arr, metrics=metrics_list)
    y_prev = float(df_train[target_col].iloc[-1]) if len(df_train) > 0 else None
    forecast_eval = forecast_eval_from_fold(y_test, pred_arr, horizon=horizon, y_prev=y_prev)
    residual_features = residual_features_from_fold(y_test, pred_arr, last_k=residual_last_k)
    return list(pred_arr), metrics, forecast_eval, residual_features


def run_experiment(
    config: dict,
    symbol: str | None = None,
    model_instance: BaseForecaster | None = None,
    adapter_name: str | None = None,
) -> dict:
    """
    Load data, run walk-forward (or single train/test), aggregate metrics, return results.

    Does not call Supabase, ForecastServiceV2, or ForecastSynthesizer.
    """
    adapter_name = adapter_name or config.get("data_adapter", "yfinance")
    symbols = [symbol] if symbol else config.get("symbols", ["AAPL"])
    horizon = config.get("horizon", 5)
    metrics_list = config.get("metrics", ["directional_accuracy", "mae", "mse"])
    wf = config.get("walk_forward", {})
    train_size = wf.get("train_size", 252)
    test_size = wf.get("test_size", 21)
    step_size = wf.get("step_size", 21)

    adapter = get_adapter(adapter_name)
    target_col = "close"

    # model_factory: returns a fresh instance per fold (avoids fold leakage)
    if model_instance is not None:
        model_factory = type(model_instance)
    else:
        model_name = config.get("model", "naive")
        hc = config.get("hybrid_config", {})
        if model_name == "hybrid":
            from forecasting_lab.models.hybrid_ensemble_forecaster import HybridEnsembleForecaster

            def model_factory():
                order = hc.get("arima_order", (2, 0, 2))
                if isinstance(order, list):
                    order = tuple(order)
                return HybridEnsembleForecaster(
                    xgb_weight=float(hc.get("xgb_weight", 0.6)),
                    arima_weight=float(hc.get("arima_weight", 0.4)),
                    arima_order=order,
                    divergence_threshold=hc.get("divergence_threshold", 0.15),
                )
        else:
            from forecasting_lab.models.registry import get as get_model
            model_factory = lambda: get_model(model_name)

    # Splitter selection (optional purged walk-forward)
    use_purged = bool(config.get("use_purged_walk_forward", False))
    embargo_pct = float(config.get("embargo_pct", 0.05))
    if use_purged:
        from forecasting_lab.evaluation.purged_walk_forward import purged_walk_forward_splits as _splits
    else:
        _splits = walk_forward_splits

    # Monitoring (optional)
    enable_monitoring = bool(config.get("enable_monitoring", False))
    monitor = None
    monitor_events: list[dict] = []
    if enable_monitoring:
        from forecasting_lab.evaluation.model_monitor import ModelMonitor
        thresholds = config.get("alert_thresholds", {
            "mae_degradation": 15.0,
            "accuracy_drop": 0.50,
            "drift_threshold": 0.05,
            "latency_threshold": 100.0,
        })
        monitor = ModelMonitor(thresholds)

    all_results: list[dict] = []
    for sym in symbols:
        df = adapter.load(sym, start=config.get("start"), end=config.get("end"), timeframe=config.get("timeframe"))
        if df is None or len(df) < train_size + test_size:
            all_results.append({"symbol": sym, "error": "Insufficient data", "metrics": {}})
            continue

        df = df.sort_values("ts").reset_index(drop=True)
        if target_col not in df.columns:
            all_results.append({"symbol": sym, "error": f"Missing column {target_col}", "metrics": {}})
            continue
        y = df[target_col]
        X = df.drop(columns=[target_col], errors="ignore")

        fold_metrics: list[dict] = []
        fold_evals: list[dict] = []
        last_residual_features: dict = {}

        split_kwargs = dict(train_size=train_size, test_size=test_size, step_size=step_size)
        if use_purged:
            split_kwargs["embargo_pct"] = embargo_pct

        for train_slice, test_slice in _splits(X, y, **split_kwargs):
            df_train = df.iloc[train_slice]
            df_test = df.iloc[test_slice]
            model = model_factory()
            try:
                _, m, fe, rf = run_one_fold(
                    model, df_train, df_test, horizon, target_col,
                    residual_last_k=config.get("residual_last_k", 5),
                    metrics_list=metrics_list,
                )
                fold_metrics.append(m)
                fold_evals.append(fe)
                last_residual_features = rf

                if monitor is not None and m:
                    if not monitor.baseline:
                        monitor.update_baseline(m)
                    else:
                        status, alerts = monitor.check_health(m)
                        monitor_events.append({
                            "symbol": sym,
                            "status": status,
                            "alerts": [a.to_dict() for a in alerts],
                            "metrics": m,
                        })

            except Exception as e:
                fold_metrics.append({"error": str(e)})

        if not fold_metrics:
            all_results.append({"symbol": sym, "error": "No folds", "metrics": {}})
            continue

        valid = [m for m in fold_metrics if "error" not in m]
        if not valid:
            all_results.append({"symbol": sym, "error": "All folds failed", "metrics": {}})
            continue

        agg = {k: sum(m[k] for m in valid) / len(valid) for k in metrics_list if k in valid[0]}
        forecast_eval = aggregate_forecast_eval(fold_evals, horizon) if fold_evals else {}
        residual_features = last_residual_features
        out_sym = {
            "symbol": sym,
            "n_folds": len(valid),
            "metrics": agg,
            "forecast_eval": forecast_eval,
            "residual_features": residual_features,
        }
        if enable_monitoring:
            out_sym["monitoring"] = {
                "enabled": True,
                "events": [e for e in monitor_events if e.get("symbol") == sym],
            }
        all_results.append(out_sym)

    return {
        "config": {k: v for k, v in config.items() if k not in ("symbols",)},
        "results": all_results,
        "run_at": datetime.utcnow().isoformat() + "Z",
    }


def _grid_candidates(grid: dict) -> list[dict]:
    """Yield dicts of param combinations from hybrid_grid config."""
    import itertools
    keys = list(grid.keys())
    if not keys:
        return [{}]
    values = [grid[k] if isinstance(grid[k], list) else [grid[k]] for k in keys]
    combos = list(itertools.product(*values))
    return [dict(zip(keys, c)) for c in combos]


def run_hybrid_tune(
    config: dict,
    symbol: str | None = None,
) -> dict:
    """
    Run grid search over hybrid_config params; select best by tune_metric.
    Requires hybrid_grid in config with xgb_weight, arima_order, tune_metric.
    """
    grid_cfg = config.get("hybrid_grid", {})
    if not grid_cfg:
        return run_experiment(config, symbol=symbol)

    tune_metric = grid_cfg.get("tune_metric", "mae")
    higher_is_better = tune_metric == "directional_accuracy"
    param_keys = [k for k in grid_cfg.keys() if k != "tune_metric" and isinstance(grid_cfg.get(k), list)]
    if not param_keys:
        return run_experiment(config, symbol=symbol)

    grid = {k: grid_cfg[k] for k in param_keys}
    candidates = _grid_candidates(grid)
    best_result = None
    best_score = float("-inf") if higher_is_better else float("inf")
    best_params: dict | None = None
    all_scores: list[dict] = []

    for params in candidates:
        cfg = dict(config)
        hc = dict(cfg.get("hybrid_config", {}))
        for k, v in params.items():
            hc[k] = tuple(v) if k == "arima_order" and isinstance(v, list) else v
        cfg["hybrid_config"] = hc
        result = run_experiment(cfg, symbol=symbol)
        agg = {}
        for r in result.get("results", []):
            m = r.get("metrics", {})
            for k, val in m.items():
                agg[k] = agg.get(k, 0) + val
        n = len(result.get("results", []))
        if n > 0:
            score = sum(r.get("metrics", {}).get(tune_metric, 0) for r in result["results"]) / n
        else:
            score = float("-inf") if higher_is_better else float("inf")
        all_scores.append({"params": params, "score": score, tune_metric: score})
        if (higher_is_better and score > best_score) or (not higher_is_better and score < best_score):
            best_score = score
            best_result = result
            best_params = params

    if best_result is not None:
        best_result["tune"] = {
            "tune_metric": tune_metric,
            "best_params": best_params,
            "best_score": best_score,
            "all_scores": all_scores,
        }
    return best_result or run_experiment(config, symbol=symbol)


def main() -> int:
    parser = argparse.ArgumentParser(description="Forecasting Lab: run experiment (no production deps)")
    parser.add_argument("--config", type=Path, default=LAB_ROOT / "config" / "default.yaml", help="Config YAML")
    parser.add_argument("--symbol", type=str, help="Override symbol")
    parser.add_argument("--model", type=str, default="naive", help="Model name (e.g. naive, hybrid)")
    parser.add_argument("--tune", action="store_true", help="Run hybrid grid search (requires hybrid_grid in config)")
    parser.add_argument("--out-dir", type=Path, default=LAB_ROOT / "results", help="Results directory")
    args = parser.parse_args()

    config = load_config(args.config)
    config["model"] = args.model

    if args.tune and config.get("model") == "hybrid":
        result = run_hybrid_tune(config, symbol=args.symbol)
    else:
        result = run_experiment(config, symbol=args.symbol)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = args.out_dir / f"run_{stamp}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Results written to {out_path}")
    if args.tune and "tune" in result:
        print(f"Best params: {result['tune'].get('best_params')} (score={result['tune'].get('best_score'):.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
