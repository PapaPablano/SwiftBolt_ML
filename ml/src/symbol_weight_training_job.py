import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _get_db_and_settings():
    ml_root = str(Path(__file__).parent.parent)
    if ml_root not in sys.path:
        sys.path.insert(0, ml_root)

    from config.settings import settings
    from src.data.supabase_db import db

    return db, settings


def _normalize3(
    a: float,
    b: float,
    c: float,
) -> tuple[float, float, float] | None:
    a = float(max(0.0, a))
    b = float(max(0.0, b))
    c = float(max(0.0, c))
    s = a + b + c
    if s <= 0:
        return None
    return (a / s, b / s, c / s)


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def _walk_forward_layer_weights(
    evals: pd.DataFrame,
    embargo_days: int = 5,
    step: float = 0.05,
    min_train: int = 15,
) -> tuple[dict[str, float] | None, dict[str, float]]:
    required = [
        "forecast_date",
        "evaluation_date",
        "realized_price",
        "synth_supertrend_component",
        "synth_polynomial_component",
        "synth_ml_component",
    ]
    if any(c not in evals.columns for c in required):
        return None, {"reason": "missing_columns"}

    df = evals[required].copy()
    df["forecast_date"] = pd.to_datetime(df["forecast_date"], errors="coerce")
    df["evaluation_date"] = pd.to_datetime(
        df["evaluation_date"],
        errors="coerce",
    )
    for c in required[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna()
    df = df.sort_values("forecast_date").reset_index(drop=True)
    if len(df) < (min_train + 1):
        return None, {"reason": "insufficient_samples"}

    w_candidates: list[tuple[float, float, float]] = []
    grid = np.arange(0.0, 1.0 + 1e-9, step)
    for w_st in grid:
        for w_sr in grid:
            w_ml = 1.0 - w_st - w_sr
            if w_ml < -1e-9:
                continue
            w = _normalize3(w_st, w_sr, w_ml)
            if w is None:
                continue
            w_candidates.append(w)

    errors: dict[tuple[float, float, float], list[float]] = {w: [] for w in w_candidates}

    embargo = pd.Timedelta(days=int(max(0, embargo_days)))

    for i in range(min_train, len(df)):
        test = df.iloc[i]
        cutoff = test["forecast_date"] - embargo
        train = df[df["forecast_date"] < cutoff]
        if len(train) < min_train:
            continue

        y_true = np.array([float(test["realized_price"])], dtype=float)
        st = float(test["synth_supertrend_component"])
        sr = float(test["synth_polynomial_component"])
        ml = float(test["synth_ml_component"])
        x = np.array([st, sr, ml], dtype=float)

        for w in w_candidates:
            y_pred = np.array([x[0] * w[0] + x[1] * w[1] + x[2] * w[2]])
            errors[w].append(_mae(y_true, y_pred))

    scored = [(w, float(np.mean(v))) for w, v in errors.items() if v]
    if not scored:
        return None, {"reason": "no_valid_folds"}

    best_w, best_mae = min(scored, key=lambda t: t[1])
    weights = {
        "supertrend_component": best_w[0],
        "sr_component": best_w[1],
        "ensemble_component": best_w[2],
    }
    diag = {
        "oos_mae": float(best_mae),
        "n_folds": int(len(errors[best_w])),
        "embargo_days": int(embargo_days),
        "grid_step": float(step),
    }
    return weights, diag


def _normalize_nonneg(weights: dict[str, float]) -> dict[str, float]:
    w = {k: max(0.0, float(v)) for k, v in weights.items()}
    s = sum(w.values())
    if s <= 0:
        n = len(w)
        if n == 0:
            return {}
        return {k: 1.0 / n for k in w}
    return {k: v / s for k, v in w.items()}


def _fit_component_weights(evals: pd.DataFrame) -> dict[str, float] | None:
    cols = [
        "synth_supertrend_component",
        "synth_polynomial_component",
        "synth_ml_component",
        "realized_price",
    ]
    if any(c not in evals.columns for c in cols):
        return None

    df = evals[cols].copy()
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna()
    if df.empty:
        return None

    e_st = np.mean(np.abs(df["synth_supertrend_component"] - df["realized_price"]))
    e_sr = np.mean(np.abs(df["synth_polynomial_component"] - df["realized_price"]))
    e_ml = np.mean(np.abs(df["synth_ml_component"] - df["realized_price"]))

    eps = 1e-9
    raw = {
        "supertrend_component": 1.0 / (e_st + eps),
        "sr_component": 1.0 / (e_sr + eps),
        "ensemble_component": 1.0 / (e_ml + eps),
    }
    return _normalize_nonneg(raw)


def _fit_rf_gb_weights(evals: pd.DataFrame) -> tuple[float, float] | None:
    if "rf_correct" not in evals.columns or "gb_correct" not in evals.columns:
        return None

    rf = pd.to_numeric(evals["rf_correct"], errors="coerce")
    gb = pd.to_numeric(evals["gb_correct"], errors="coerce")
    m = rf.notna() & gb.notna()
    rf = rf[m]
    gb = gb[m]
    if len(rf) < 5:
        return None

    rf_acc = float(rf.mean())
    gb_acc = float(gb.mean())
    denom = rf_acc + gb_acc
    if denom <= 0:
        return (0.5, 0.5)

    return (rf_acc / denom, gb_acc / denom)


def train_symbol_weights(
    symbol: str,
    horizon: str,
    lookback_days: int = 365,
) -> None:
    db, _ = _get_db_and_settings()
    symbol_id = db.get_symbol_id(symbol)

    default_synth = {
        "layer_weights": {
            "supertrend_component": 0.35,
            "sr_component": 0.35,
            "ensemble_component": 0.30,
        }
    }

    eval_rows = (
        db.client.table("forecast_evaluations")
        .select(
            "forecast_date, evaluation_date, realized_price, "
            "rf_correct, gb_correct, "
            "synth_supertrend_component, synth_polynomial_component, "
            "synth_ml_component"
        )
        .eq("symbol", symbol.upper())
        .eq("horizon", horizon)
        .gte(
            "evaluation_date",
            (pd.Timestamp.now('UTC') - pd.Timedelta(days=lookback_days)).isoformat(),
        )
        .order("evaluation_date", desc=True)
        .limit(500)
        .execute()
    )

    evals = pd.DataFrame(eval_rows.data or [])
    if evals.empty:
        diagnostics = {
            "trained_at": datetime.utcnow().isoformat(),
            "n_samples": 0,
            "lookback_days": int(lookback_days),
            "method": "seed_default",
        }
        db.upsert_symbol_model_weights(
            symbol_id=symbol_id,
            horizon=horizon,
            rf_weight=0.5,
            gb_weight=0.5,
            synth_weights=default_synth,
            diagnostics=diagnostics,
        )
        logger.info(
            "Seeded symbol_model_weights for %s (%s)",
            symbol,
            horizon,
        )
        return

    try:
        min_train = int(os.getenv("WEIGHT_TRAIN_MIN_SAMPLES", "30"))
    except Exception:
        min_train = 30

    rf_gb = _fit_rf_gb_weights(evals)
    synth_layer = None
    method = "heuristic"
    diag_extra: dict[str, float] = {}

    if len(evals) >= min_train:
        w, d = _walk_forward_layer_weights(
            evals,
            embargo_days=5,
            step=0.05,
            min_train=max(3, min_train // 2),
        )
        if w is not None:
            synth_layer = w
            method = "walk_forward_grid"
            diag_extra = d
        else:
            synth_layer = _fit_component_weights(evals)
            method = "heuristic_inverse_mae"
            diag_extra = {"fallback": 1.0}
    else:
        synth_layer = _fit_component_weights(evals)
        method = "heuristic_inverse_mae"
        diag_extra = {"fallback": 1.0}

    diagnostics = {
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": int(len(evals)),
        "lookback_days": int(lookback_days),
        "method": method,
    }
    diagnostics.update(diag_extra)

    synth_weights = {}
    if synth_layer is not None:
        synth_weights["layer_weights"] = synth_layer
    else:
        synth_weights = default_synth

    if rf_gb is not None or synth_weights:
        rf_weight = rf_gb[0] if rf_gb is not None else None
        gb_weight = rf_gb[1] if rf_gb is not None else None
        db.upsert_symbol_model_weights(
            symbol_id=symbol_id,
            horizon=horizon,
            rf_weight=rf_weight,
            gb_weight=gb_weight,
            synth_weights=synth_weights if synth_weights else None,
            diagnostics=diagnostics,
        )
        logger.info(
            "Updated symbol_model_weights for %s (%s)",
            symbol,
            horizon,
        )


def main() -> None:
    db, settings = _get_db_and_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    rows = db.client.table("watchlist_items").select("symbol_id(ticker)").execute()
    symbols = sorted(
        {
            row.get("symbol_id", {}).get("ticker")
            for row in (rows.data or [])
            if row.get("symbol_id", {}).get("ticker")
        }
    )

    for symbol in symbols:
        for horizon in ["1D", "1W", "1M"]:
            try:
                train_symbol_weights(symbol, horizon=horizon, lookback_days=365)
            except Exception as e:
                logger.warning(
                    "Weight training failed for %s (%s): %s",
                    symbol,
                    horizon,
                    e,
                )


if __name__ == "__main__":
    main()
