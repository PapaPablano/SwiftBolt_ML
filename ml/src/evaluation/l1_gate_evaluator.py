"""
L1 Gate Evaluator - Validates 15m 4-bar forecast vs no-change baseline.

Walk-forward evaluation with Diebold-Mariano statistical test.
Option A: final bar only (actual_4, pred_4, base_4).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.evaluation.statistical_tests import (
    HypothesisTestResult,
    StatisticalSignificanceTester,
)
from src.features.support_resistance_detector import SupportResistanceDetector
from src.features.technical_indicators import add_technical_features
from src.forecast_synthesizer import ForecastSynthesizer
from src.forecast_weights import get_default_weights
from src.models.baseline_forecaster import BaselineForecaster
from src.models.ensemble_forecaster import EnsembleForecaster
from src.models.xgboost_forecaster import XGBoostForecaster
from src.strategies.supertrend_ai import SuperTrendAI

logger = logging.getLogger(__name__)

# 15m config: import from source of truth to avoid drift from HORIZON_CONFIG
try:
    from src.intraday_forecast_job import HORIZON_CONFIG

    _cfg = HORIZON_CONFIG.get("15m", {})
    LOOKAHEAD_BARS = int(_cfg.get("forecast_bars", 4))
    TIME_SCALE_DAYS = _cfg.get("horizon_days")
    if TIME_SCALE_DAYS is None:
        TIME_SCALE_DAYS = LOOKAHEAD_BARS * 15 * 60 / 86400.0
    MIN_TRAINING_BARS = int(_cfg.get("min_training_bars", 60))
except ImportError:
    LOOKAHEAD_BARS = 4
    TIME_SCALE_DAYS = LOOKAHEAD_BARS * 15 * 60 / 86400.0
    MIN_TRAINING_BARS = 60

XGB_WEIGHT = 0.2
MIN_XGB_PER_CLASS = 5


def _convert_sr_to_synthesizer_format(sr_levels: dict, current_price: float) -> dict:
    """Convert S/R detector output to synthesizer format."""
    indicators = sr_levels.get("indicators", {})

    poly_in = indicators.get("polynomial", {})
    polynomial = {
        "support": poly_in.get("current_support", current_price * 0.95),
        "resistance": poly_in.get("current_resistance", current_price * 1.05),
        "supportSlope": poly_in.get("support_slope", 0),
        "resistanceSlope": poly_in.get("resistance_slope", 0),
        "supportTrend": "rising" if poly_in.get("support_slope", 0) > 0 else "falling",
        "resistanceTrend": "rising" if poly_in.get("resistance_slope", 0) > 0 else "falling",
        "forecastSupport": poly_in.get("forecast_support", []),
        "forecastResistance": poly_in.get("forecast_resistance", []),
        "isDiverging": poly_in.get("is_diverging", False),
        "isConverging": poly_in.get("is_converging", False),
    }

    logistic_in = indicators.get("logistic", {})
    logistic = {
        "supportLevels": [
            {"level": lvl.get("level", 0), "probability": lvl.get("probability", 0.5)}
            for lvl in logistic_in.get("support_levels", [])
        ],
        "resistanceLevels": [
            {"level": lvl.get("level", 0), "probability": lvl.get("probability", 0.5)}
            for lvl in logistic_in.get("resistance_levels", [])
        ],
        "signals": logistic_in.get("signals", []),
    }

    pivot_in = indicators.get("pivot_levels", {})
    pivot_levels_list = pivot_in.get("pivot_levels", [])
    pivot_levels = {}
    for pl in pivot_levels_list:
        period = pl.get("period", 5)
        key = f"period{period}"
        pivot_levels[key] = {
            "high": pl.get("high"),
            "low": pl.get("low"),
            "highStatus": pl.get("high_status", "active"),
            "lowStatus": pl.get("low_status", "active"),
        }

    for period in [5, 25, 50, 100]:
        key = f"period{period}"
        if key not in pivot_levels:
            pivot_levels[key] = {
                "high": current_price * 1.02,
                "low": current_price * 0.98,
                "highStatus": "active",
                "lowStatus": "active",
            }

    return {
        "pivotLevels": pivot_levels,
        "polynomial": polynomial,
        "logistic": logistic,
        "nearestSupport": sr_levels.get("nearest_support", current_price * 0.95),
        "nearestResistance": sr_levels.get("nearest_resistance", current_price * 1.05),
        "anchorZones": sr_levels.get("anchor_zones", {}),
        "movingAverages": (sr_levels.get("moving_averages") or {}).get("levels", []),
        "fibonacci": sr_levels.get("fibonacci", {}),
        "ichimoku": sr_levels.get("ichimoku", {}),
    }


def _convert_supertrend_to_synthesizer_format(st_info: dict) -> dict:
    """Convert SuperTrend output to synthesizer format."""
    return {
        "current_trend": st_info.get("current_trend", "NEUTRAL"),
        "signal_strength": st_info.get("signal_strength", 5),
        "performance_index": st_info.get("performance_index", 0.5),
        "atr": st_info.get("atr"),
    }


def _predict_at_origin(
    df: pd.DataFrame,
    symbol: str = "L1_GATE",
    pre_featured: bool = False,
) -> Optional[float]:
    """
    Run full 15m L1 pipeline on df; return synth_result.target (pred_4) or None.

    Matches production path: indicators, S/R, SuperTrend, baseline, ensemble, synthesizer.
    No DB writes. When pre_featured=True, skips add_technical_features (caller computed once).
    """
    if len(df) < MIN_TRAINING_BARS or "close" not in df.columns:
        return None

    try:
        if pre_featured:
            df_work = df.copy()
        else:
            df_work = add_technical_features(df.copy())

        current_price = float(df_work["close"].iloc[-1])

        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df_work)
        sr_response = _convert_sr_to_synthesizer_format(sr_levels, current_price)

        try:
            supertrend = SuperTrendAI(df_work)
            _, st_info_raw = supertrend.calculate()
        except Exception as e:
            logger.debug("SuperTrend failed for %s: %s", symbol, e)
            st_info_raw = {
                "current_trend": "NEUTRAL",
                "signal_strength": 5,
                "performance_index": 0.5,
                "atr": current_price * 0.01,
            }

        st_for_synth = _convert_supertrend_to_synthesizer_format(st_info_raw)

        baseline = BaselineForecaster()
        X, y = baseline.prepare_training_data(df_work, horizon_days=float(LOOKAHEAD_BARS))

        if len(X) < MIN_TRAINING_BARS:
            return None

        unique_labels = y.unique() if hasattr(y, "unique") else np.unique(y)
        if len(unique_labels) < 2:
            return None

        forecaster = EnsembleForecaster(horizon="1D", symbol_id=None, use_db_weights=False)
        forecaster.train(X, y)
        ensemble_pred = forecaster.predict(X.tail(1))

        if XGB_WEIGHT > 0 and XGB_WEIGHT < 1:
            try:
                y_binary = y.map(
                    lambda v: "bullish" if str(v).lower() == "bullish" else "bearish"
                )
                n_bull = int((y_binary == "bullish").sum())
                n_bear = int((y_binary == "bearish").sum())
                if (
                    n_bull >= MIN_XGB_PER_CLASS
                    and n_bear >= MIN_XGB_PER_CLASS
                    and len(X) >= MIN_TRAINING_BARS
                ):
                    xgb = XGBoostForecaster()
                    xgb.train(X, y_binary, min_samples=MIN_TRAINING_BARS)
                    proba = xgb.predict_proba(X.tail(1))
                    if proba is not None and len(proba) > 0:
                        p = float(proba[0])
                        E = ensemble_pred.get("probabilities") or {}
                        for k in ("bullish", "neutral", "bearish"):
                            E[k] = float(E.get(k, 0.0))
                        X_dict = {"bullish": p, "bearish": 1.0 - p, "neutral": 0.0}
                        P_blend = {
                            k: (1.0 - XGB_WEIGHT) * E[k] + XGB_WEIGHT * X_dict[k]
                            for k in ("bullish", "neutral", "bearish")
                        }
                        total = sum(P_blend.values())
                        if total > 0:
                            for k in P_blend:
                                P_blend[k] /= total
                            label_key = max(P_blend, key=P_blend.get)
                            ensemble_pred["label"] = label_key.capitalize()
                            ensemble_pred["confidence"] = P_blend[label_key]
                            ensemble_pred["probabilities"] = P_blend
            except Exception as e:
                logger.debug("XGB blend skipped: %s", e)

        if ensemble_pred is None:
            return None

        weights = get_default_weights()
        synthesizer = ForecastSynthesizer(weights=weights)
        synth_result = synthesizer.generate_forecast(
            current_price=current_price,
            df=df_work,
            supertrend_info=st_for_synth,
            sr_response=sr_response,
            ensemble_result=ensemble_pred,
            horizon_days=TIME_SCALE_DAYS,
            symbol=symbol,
            timeframe="m15",
        )

        return float(synth_result.target)

    except Exception as e:
        logger.debug("predict_at_origin failed: %s", e)
        return None


class L1GateEvaluator:
    """
    Walk-forward evaluator for 15m 4-bar L1 forecast vs no-change baseline.

    Option A: final bar only. Pass/fail: DM p-value < 0.05 AND mean(d) < 0.

    Baseline origin convention (must match production trigger):
    - baseline_after_close_t=True (default): forecast origin = after close of bar t
      is known; last_close = close[t]. Use when production runs after bar t closes.
    - baseline_after_close_t=False: last_close = close[t-1]. Use when production
      runs at open of bar t (before bar t closes) so last known close is t-1.
    """

    def __init__(
        self,
        train_bars: int = 500,
        test_bars: int = 50,
        step_bars: int = 25,
        max_origins_per_symbol: int = 50,
        baseline_after_close_t: bool = True,
    ):
        self.train_bars = train_bars
        self.test_bars = test_bars
        self.step_bars = step_bars
        self.max_origins_per_symbol = max_origins_per_symbol
        self.baseline_after_close_t = baseline_after_close_t
        self.tester = StatisticalSignificanceTester()

    def compute_loss_series(self, symbol: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Walk-forward: for each test origin, get L1 pred, baseline, actual; compute loss.

        Returns:
            DataFrame with columns: symbol, origin_ts, actual_4, pred_4, base_4,
            L_model, L_baseline, d
        """
        if "ts" not in df.columns:
            df = df.reset_index()
        df = df.sort_values("ts").reset_index(drop=True)

        min_len = self.train_bars + self.test_bars + LOOKAHEAD_BARS
        if len(df) < min_len:
            logger.warning(
                "%s: insufficient data %d < %d", symbol, len(df), min_len
            )
            return pd.DataFrame()

        # Compute indicators once for full df (slice per origin; no leakage)
        df_featured = add_technical_features(df.copy())

        rows = []
        origins_count = 0

        for start in range(
            self.train_bars,
            len(df) - self.test_bars - LOOKAHEAD_BARS + 1,
            self.step_bars,
        ):
            if origins_count >= self.max_origins_per_symbol:
                break

            test_end = min(start + self.test_bars, len(df) - LOOKAHEAD_BARS)

            for t in range(start, test_end):
                if origins_count >= self.max_origins_per_symbol:
                    break

                if t + LOOKAHEAD_BARS >= len(df):
                    continue

                df_slice = df_featured.iloc[: t + 1].copy()

                pred_4 = _predict_at_origin(
                    df_slice, symbol=symbol, pre_featured=True
                )
                if pred_4 is None:
                    continue

                # Baseline: no-change forecast. Match production trigger convention.
                if self.baseline_after_close_t:
                    last_close = float(df["close"].iloc[t])  # after close of bar t
                else:
                    last_close = float(df["close"].iloc[t - 1])  # before close of bar t
                # Index alignment guardrail: origin_ts from t, actual_4 from t+LOOKAHEAD_BARS
                # (Use LOOKAHEAD_BARS not t+4 to avoid off-by-one after reindexing)
                idx_actual = t + LOOKAHEAD_BARS
                assert idx_actual < len(df), "actual_4 index must be within df"
                origin_ts_raw = df["ts"].iloc[t]
                actual_4 = float(df["close"].iloc[idx_actual])
                # Sanity: origin_ts must equal timestamp at t
                origin_ts = origin_ts_raw
                if hasattr(origin_ts, "isoformat"):
                    origin_ts = origin_ts.isoformat()
                base_4 = last_close

                L_model = float(np.abs(actual_4 - pred_4))
                L_baseline = float(np.abs(actual_4 - base_4))
                d = L_model - L_baseline

                rows.append(
                    {
                        "symbol": symbol,
                        "origin_ts": origin_ts,
                        "actual_4": actual_4,
                        "pred_4": pred_4,
                        "base_4": base_4,
                        "L_model": L_model,
                        "L_baseline": L_baseline,
                        "d": d,
                    }
                )
                origins_count += 1

            if origins_count >= self.max_origins_per_symbol:
                break

        return pd.DataFrame(rows)

    MIN_ORIGINS_FOR_POWER = 100

    def run_dm_test(self, loss_df: pd.DataFrame) -> HypothesisTestResult:
        """
        Run Diebold-Mariano test on loss differential series.

        Given loss_df with actual_4, pred_4, base_4 columns.
        Fails fast if n_origins < 100 (insufficient sample size for reliable p-value).
        """
        n = len(loss_df)
        if n < 2:
            return HypothesisTestResult(
                test_name="Diebold-Mariano test",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                interpretation="Insufficient samples for DM test",
            )

        if n < self.MIN_ORIGINS_FOR_POWER:
            return HypothesisTestResult(
                test_name="Diebold-Mariano test",
                statistic=float("nan"),
                p_value=float("nan"),
                is_significant=False,
                effect_size=float(np.mean(loss_df["d"])) if "d" in loss_df.columns else 0.0,
                interpretation=f"Insufficient sample size: n_origins={n} < {self.MIN_ORIGINS_FOR_POWER}; "
                "fail fast rather than returning noisy p-value",
            )

        y_true = np.asarray(loss_df["actual_4"].values, dtype=float)
        y_pred1 = np.asarray(loss_df["pred_4"].values, dtype=float)
        y_pred2 = np.asarray(loss_df["base_4"].values, dtype=float)

        return self.tester.diebold_mariano_test(
            y_true,
            y_pred1,
            y_pred2,
            loss_function="absolute",
            max_lags=LOOKAHEAD_BARS - 1,  # HAC for h=4 overlapping targets
        )
