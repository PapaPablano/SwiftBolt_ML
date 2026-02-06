"""MenthorQ-style features: GEX, DEX, VRP, skew.

Formulas (Perfiliev/MenthorQ):
- GEX: sum(OI * gamma * 100 * S^2) — dealer long gamma = positive GEX
- DEX: sum(OI * delta * 100 * S) — per strike or bucket
- VRP: IV - RV (or IV/RV) — positive favors selling vol, negative favors buying
- Skew: 25-delta risk reversal or put-minus-call IV at nearest strikes

Use as regime/context signals, not direct buy/sell triggers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MenthorQFeatures:
    """MenthorQ-style feature bundle."""

    gex_0_7_dte: float = 0.0
    gex_8_30_dte: float = 0.0
    gex_30_90_dte: float = 0.0
    dex_0_7_dte: float = 0.0
    dex_8_30_dte: float = 0.0
    dex_30_90_dte: float = 0.0
    vrp: float = 0.0  # IV - RV (annualized)
    skew_proxy: float = 0.0  # put IV - call IV at ~25 delta
    iv_avg: float = 0.0
    rv: float = 0.0


def _get_dte(row: pd.Series, reference_ts: float | None = None) -> int:
    """Compute DTE from expiration (Unix seconds or date string)."""
    import time as _time
    ref = reference_ts or _time.time()
    exp = row.get("expiration") or row.get("expiry")
    if exp is None or pd.isna(exp):
        return 0
    try:
        if isinstance(exp, (int, float)) and exp > 1e9:
            exp_ts = float(exp)
        else:
            exp_ts = pd.Timestamp(str(exp)).timestamp()
        return max(0, int((exp_ts - ref) / 86400))
    except Exception:
        return 0


def compute_gex_dex(
    options_df: pd.DataFrame,
    spot: float,
    reference_ts: float | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Compute GEX and DEX by DTE bucket.

    GEX = sum(OI * gamma * 100 * S^2)
    DEX = sum(OI * delta * 100 * S)

    Buckets: 0-7, 8-30, 30-90 DTE.
    """
    if options_df.empty:
        return (
            {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0},
            {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0},
        )

    df = options_df.copy()
    oi_col = "open_interest" if "open_interest" in df.columns else "openInterest"
    if oi_col not in df.columns:
        return (
            {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0},
            {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0},
        )

    df["dte"] = df.apply(lambda r: _get_dte(r, reference_ts), axis=1)
    df["gex"] = df[oi_col].fillna(0) * df.get("gamma", 0).fillna(0) * 100 * (spot ** 2)
    df["dex"] = df[oi_col].fillna(0) * df.get("delta", 0).fillna(0) * 100 * spot

    gex: dict[str, float] = {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0}
    dex: dict[str, float] = {"0_7": 0.0, "8_30": 0.0, "30_90": 0.0}

    for _, row in df.iterrows():
        dte = row["dte"]
        g_val = row["gex"]
        d_val = row["dex"]
        if dte <= 7:
            gex["0_7"] += g_val
            dex["0_7"] += d_val
        elif dte <= 30:
            gex["8_30"] += g_val
            dex["8_30"] += d_val
        elif dte <= 90:
            gex["30_90"] += g_val
            dex["30_90"] += d_val

    return gex, dex


def compute_vrp(iv: float, rv: float) -> float:
    """VRP = IV - RV (annualized). Positive favors selling vol."""
    if not np.isfinite(iv) or not np.isfinite(rv):
        return 0.0
    return float(iv - rv)


def compute_skew_proxy(
    options_df: pd.DataFrame,
    spot: float,
) -> float:
    """
    Skew proxy: put IV minus call IV at ~ATM / nearest 25-delta strikes.

    Positive = put skew (puts rich vs calls).
    """
    if options_df.empty:
        return 0.0

    df = options_df.copy()
    iv_col = "iv" if "iv" in df.columns else "impliedVolatility"
    if iv_col not in df.columns:
        iv_col = "implied_vol"
    if iv_col not in df.columns:
        return 0.0

    calls = df[df.get("side", df.get("option_type", "")) == "call"]
    puts = df[df.get("side", df.get("option_type", "")) == "put"]

    if calls.empty or puts.empty:
        return 0.0

    # ATM: closest strike to spot
    call_strikes = calls["strike"].unique()
    put_strikes = puts["strike"].unique()
    atm_call = min(call_strikes, key=lambda k: abs(float(k) - spot)) if len(call_strikes) else None
    atm_put = min(put_strikes, key=lambda k: abs(float(k) - spot)) if len(put_strikes) else None

    call_iv = calls[calls["strike"] == atm_call][iv_col].mean() if atm_call is not None else np.nan
    put_iv = puts[puts["strike"] == atm_put][iv_col].mean() if atm_put is not None else np.nan

    if np.isnan(call_iv) or np.isnan(put_iv):
        return 0.0

    return float(put_iv - call_iv)


def compute_menthorq_features(
    options_df: pd.DataFrame,
    spot: float,
    realized_vol: float | None = None,
    reference_ts: float | None = None,
) -> MenthorQFeatures:
    """
    Compute full MenthorQ feature bundle from options chain.

    Args:
        options_df: Options chain with OI, gamma, delta, iv
        spot: Underlying price
        realized_vol: Realized volatility (annualized) for VRP
        reference_ts: Unix seconds for DTE

    Returns:
        MenthorQFeatures
    """
    gex, dex = compute_gex_dex(options_df, spot, reference_ts)
    skew = compute_skew_proxy(options_df, spot)

    iv_col = "iv" if "iv" in options_df.columns else "impliedVolatility"
    if iv_col not in options_df.columns:
        iv_col = "implied_vol"
    iv_avg = float(options_df[iv_col].mean()) if iv_col in options_df.columns and len(options_df) > 0 else 0.0
    rv = realized_vol if realized_vol is not None and np.isfinite(realized_vol) else 0.0
    vrp = compute_vrp(iv_avg, rv)

    return MenthorQFeatures(
        gex_0_7_dte=gex["0_7"],
        gex_8_30_dte=gex["8_30"],
        gex_30_90_dte=gex["30_90"],
        dex_0_7_dte=dex["0_7"],
        dex_8_30_dte=dex["8_30"],
        dex_30_90_dte=dex["30_90"],
        vrp=vrp,
        skew_proxy=skew,
        iv_avg=iv_avg,
        rv=rv,
    )


def to_dict(f: MenthorQFeatures) -> dict[str, Any]:
    """Convert MenthorQFeatures to dict for ranker/API."""
    return {
        "gex_0_7_dte": f.gex_0_7_dte,
        "gex_8_30_dte": f.gex_8_30_dte,
        "gex_30_90_dte": f.gex_30_90_dte,
        "dex_0_7_dte": f.dex_0_7_dte,
        "dex_8_30_dte": f.dex_8_30_dte,
        "dex_30_90_dte": f.dex_30_90_dte,
        "vrp": f.vrp,
        "skew_proxy": f.skew_proxy,
        "iv_avg": f.iv_avg,
        "rv": f.rv,
    }
