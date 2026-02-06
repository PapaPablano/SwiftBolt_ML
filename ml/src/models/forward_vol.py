"""Forward Volatility from ATM IV Curve.

Computes forward vol between two expiries using variance additivity:
    sigma_f = sqrt((T2*sigma2^2 - T1*sigma1^2) / (T2 - T1))

Time convention: ACT/365 for T in years (consistent with options pricing).
Naming: Contango = front IV lower than back (upward slope). Backwardation = front IV higher than back (downward slope).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal  # noqa: F401

# Epsilon for flat term-structure: avoid false "backwardation" when sigma_near ≈ sigma_far
TERM_STRUCTURE_EPSILON = 0.001

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Time convention: ACT/365 (actual days / 365 for T in years)
ACT_365 = 365.0


@dataclass
class ForwardVolResult:
    """Result of forward vol computation between two expiries."""

    sigma_near: float  # ATM IV at near expiry
    sigma_far: float  # ATM IV at far expiry
    forward_vol: float  # sqrt(max(0, (T2*v2 - T1*v1)/(T2-T1)))
    term_structure_regime: Literal["contango", "backwardation", "flat"]  # contango = front low, backwardation = front high, flat = within epsilon
    low_confidence: bool  # True when raw variance numerator < 0 (noise/data issues)
    T_near_years: float  # T1 in years
    T_far_years: float  # T2 in years
    expected_move_near_pct: float  # sigma_near * sqrt(T_near) * 100
    expected_move_far_pct: float  # sigma_far * sqrt(T_far) * 100


def _extract_iv(row: pd.Series) -> float:
    """Extract IV from chain row; supports multiple column names."""
    for col in ("impliedVolatility", "implied_vol", "iv", "greek_mid_iv"):
        if col in row.index and pd.notna(row.get(col)):
            v = row[col]
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    return np.nan


def build_atm_iv_per_expiry(
    options_df: pd.DataFrame,
    spot: float,
    reference_ts: float | None = None,
    min_volume: int = 5,
    min_oi: int = 20,
) -> dict[str, float]:
    """
    Build ATM IV per expiry from options chain.

    For each expiry: find ATM strike (closest to spot), average ATM call/put IV.
    Applies liquidity filters (min volume/OI). Skips expiries with no valid IV.

    Args:
        options_df: DataFrame with strike, expiration, impliedVolatility (or iv), volume, open_interest
        spot: Current underlying price
        reference_ts: Unix seconds for T calculation; defaults to now
        min_volume: Minimum volume for inclusion
        min_oi: Minimum open interest for inclusion

    Returns:
        Dict mapping expiry key (date string or ts) -> ATM IV (annualized)
    """
    import time as _time

    if options_df.empty:
        return {}

    ref = reference_ts if reference_ts is not None else _time.time()

    # Normalize columns
    df = options_df.copy()
    if "openInterest" in df.columns and "open_interest" not in df.columns:
        df["open_interest"] = df["openInterest"]
    if "impliedVolatility" in df.columns and "iv" not in df.columns:
        df["iv"] = df["impliedVolatility"]

    result: dict[str, float] = {}

    for expiry_key, grp in df.groupby("expiration", dropna=False):
        if pd.isna(expiry_key):
            continue

        # Find ATM strike
        strikes = grp["strike"].unique()
        atm_strike = min(strikes, key=lambda k: abs(k - spot))

        # ATM contracts
        atm = grp[abs(grp["strike"] - atm_strike) < 0.01]
        if atm.empty:
            atm = grp[grp["strike"] == atm_strike]

        if atm.empty:
            continue

        # Liquidity filter (relaxed: require at least one contract with decent liquidity)
        vol_col = "volume" if "volume" in atm.columns else None
        oi_col = "open_interest" if "open_interest" in atm.columns else "openInterest"
        if vol_col and oi_col in atm.columns:
            liquid = atm[(atm[vol_col] >= min_volume) | (atm[oi_col] >= min_oi)]
            if not liquid.empty:
                atm = liquid

        ivs = []
        for _, row in atm.iterrows():
            iv = _extract_iv(row)
            if not np.isnan(iv) and iv > 0:
                ivs.append(iv)

        if ivs:
            result[str(expiry_key)] = float(np.mean(ivs))

    return result


def _expiry_to_T(expiry_ts: float, reference_ts: float) -> float:
    """Convert expiry Unix timestamp to T in years (ACT/365)."""
    seconds = max(0, expiry_ts - reference_ts)
    days = seconds / 86400.0
    return days / ACT_365


def compute_forward_vol(
    atm_iv_by_expiry: dict[str, float],
    expiry_near_ts: float,
    expiry_far_ts: float,
    spot: float,
    reference_ts: float | None = None,
) -> ForwardVolResult | None:
    """
    Compute forward vol between near and far expiries.

    Formula: sigma_f = sqrt(max(0, (T2*sigma2^2 - T1*sigma1^2) / (T2 - T1)))

    If T2*v2 - T1*v1 < 0, clamps to 0 and sets low_confidence=True.
    Term structure: contango = sigma_near < sigma_far; backwardation = sigma_near > sigma_far.

    Args:
        atm_iv_by_expiry: Dict mapping expiry key -> ATM IV (annualized)
        expiry_near_ts: Near expiry Unix seconds
        expiry_far_ts: Far expiry Unix seconds
        spot: Current underlying price (for expected move)
        reference_ts: Unix seconds for T; defaults to now

    Returns:
        ForwardVolResult or None if insufficient data
    """
    import time as _time

    ref = reference_ts if reference_ts is not None else _time.time()

    if expiry_far_ts <= expiry_near_ts:
        logger.warning("expiry_far_ts must be > expiry_near_ts")
        return None

    # Map expiries - keys may be date strings or timestamps
    def _find_sigma(ts: float) -> float | None:
        # Try direct timestamp match
        ts_str = str(int(ts))
        if ts_str in atm_iv_by_expiry:
            return atm_iv_by_expiry[ts_str]
        # Try date string from ts
        from datetime import datetime
        d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        if d in atm_iv_by_expiry:
            return atm_iv_by_expiry[d]
        # First key that matches "near" (smallest T) or "far" (largest T)
        for k, v in atm_iv_by_expiry.items():
            try:
                if "T" in str(k).upper() or "-" in str(k):
                    parsed = pd.Timestamp(k).timestamp()
                else:
                    parsed = float(k)
                if abs(parsed - ts) < 86400:  # within 1 day
                    return v
            except Exception:
                pass
        return None

    sigma1 = _find_sigma(expiry_near_ts)
    sigma2 = _find_sigma(expiry_far_ts)

    if sigma1 is None or sigma2 is None:
        # Fallback: use first two expiries by T if we have at least 2
        sorted_items = sorted(
            atm_iv_by_expiry.items(),
            key=lambda x: (
                pd.Timestamp(x[0]).timestamp() if isinstance(x[0], str) and "-" in str(x[0])
                else float(x[0]) if str(x[0]).replace(".", "").isdigit() else 0
            ),
        )
        if len(sorted_items) < 2:
            return None
        sigma1 = sorted_items[0][1]
        sigma2 = sorted_items[1][1]
        # Recompute T from first two keys if possible
        try:
            k1, k2 = sorted_items[0][0], sorted_items[1][0]
            t1_ts = pd.Timestamp(k1).timestamp() if isinstance(k1, str) else float(k1)
            t2_ts = pd.Timestamp(k2).timestamp() if isinstance(k2, str) else float(k2)
            expiry_near_ts = min(t1_ts, t2_ts)
            expiry_far_ts = max(t1_ts, t2_ts)
        except Exception:
            pass

    T1 = _expiry_to_T(expiry_near_ts, ref)
    T2 = _expiry_to_T(expiry_far_ts, ref)

    if T2 <= T1 or T1 < 0:
        return None

    v1 = T1 * (sigma1 ** 2)
    v2 = T2 * (sigma2 ** 2)
    numerator = v2 - v1
    low_confidence = numerator < 0

    if numerator < 0:
        numerator = 0.0

    denom = T2 - T1
    if denom <= 0:
        return None

    sigma_f = float(np.sqrt(numerator / denom))

    # Term structure: contango = front low, backwardation = front high, flat = within epsilon
    sigma_diff = sigma1 - sigma2
    if abs(sigma_diff) < TERM_STRUCTURE_EPSILON:
        term_structure_regime: Literal["contango", "backwardation", "flat"] = "flat"
    else:
        term_structure_regime = "contango" if sigma1 < sigma2 else "backwardation"

    # Expected move: S * sigma * sqrt(T) in percent
    expected_move_near_pct = float(sigma1 * np.sqrt(T1) * 100) if sigma1 > 0 else 0.0
    expected_move_far_pct = float(sigma2 * np.sqrt(T2) * 100) if sigma2 > 0 else 0.0

    return ForwardVolResult(
        sigma_near=float(sigma1),
        sigma_far=float(sigma2),
        forward_vol=sigma_f,
        term_structure_regime=term_structure_regime,
        low_confidence=low_confidence,
        T_near_years=T1,
        T_far_years=T2,
        expected_move_near_pct=expected_move_near_pct,
        expected_move_far_pct=expected_move_far_pct,
    )


def _expiry_to_ts(val) -> float:
    """Convert expiration value to Unix seconds."""
    if isinstance(val, (int, float)) and val > 1e9:
        return float(val)
    try:
        return pd.Timestamp(str(val)).timestamp()
    except Exception:
        return 0.0


def compute_forward_vol_from_chain(
    options_df: pd.DataFrame,
    spot: float,
    expiry_near_ts: float,
    expiry_far_ts: float,
    reference_ts: float | None = None,
) -> ForwardVolResult | None:
    """
    Convenience: build ATM IV from chain and compute forward vol.

    Handles expiration column as Unix seconds or YYYY-MM-DD.
    """
    import time as _time

    if options_df.empty or "expiration" not in options_df.columns:
        return None

    ref = reference_ts if reference_ts is not None else _time.time()

    # Build ATM IV per expiry, keyed by ts
    atm_map: dict[str, float] = {}
    for expiry_val, grp in options_df.groupby("expiration", dropna=False):
        if pd.isna(expiry_val):
            continue
        strikes = grp["strike"].dropna().unique()
        if len(strikes) == 0:
            continue
        atm_strike = float(min(strikes, key=lambda k: abs(float(k) - spot)))
        atm = grp[abs(grp["strike"].astype(float) - atm_strike) < 0.02]
        if atm.empty:
            atm = grp[grp["strike"].astype(float) == atm_strike]
        ivs = []
        for _, row in atm.iterrows():
            iv = _extract_iv(row)
            if not np.isnan(iv) and iv > 0:
                ivs.append(iv)
        if ivs:
            ts_val = _expiry_to_ts(expiry_val)
            atm_map[str(ts_val)] = float(np.mean(ivs))

    if len(atm_map) < 2:
        items = list(atm_map.items())
        if len(items) == 1:
            ts_str, sigma = items[0]
            ts = float(ts_str)
            T1 = _expiry_to_T(ts, ref)
            return ForwardVolResult(
                sigma_near=sigma,
                sigma_far=sigma,
                forward_vol=sigma,
                term_structure_regime="contango",
                low_confidence=False,
                T_near_years=max(1e-6, T1),
                T_far_years=max(1e-6, T1),
                expected_move_near_pct=sigma * np.sqrt(max(1e-6, T1)) * 100,
                expected_move_far_pct=sigma * np.sqrt(max(1e-6, T1)) * 100,
            )
        return None

    # Map expiry_near_ts and expiry_far_ts to sigma
    def _closest_key(target_ts: float) -> tuple[str, float] | None:
        best_key, best_sigma, best_diff = None, None, float("inf")
        for k, v in atm_map.items():
            ts = float(k)
            diff = abs(ts - target_ts)
            if diff < best_diff:
                best_diff = diff
                best_key = k
                best_sigma = v
        return (best_key, best_sigma) if best_key else None

    near_match = _closest_key(expiry_near_ts)
    far_match = _closest_key(expiry_far_ts)
    if not near_match or not far_match:
        return None
    _, sigma1 = near_match
    _, sigma2 = far_match

    T1 = _expiry_to_T(expiry_near_ts, ref)
    T2 = _expiry_to_T(expiry_far_ts, ref)
    if T2 <= T1 or T1 < 0:
        return None

    v1 = T1 * (sigma1 ** 2)
    v2 = T2 * (sigma2 ** 2)
    numerator = v2 - v1
    low_confidence = numerator < 0
    if numerator < 0:
        numerator = 0.0
    sigma_f = float(np.sqrt(numerator / (T2 - T1)))
    sigma_diff = sigma1 - sigma2
    if abs(sigma_diff) < TERM_STRUCTURE_EPSILON:
        term_structure_regime: Literal["contango", "backwardation", "flat"] = "flat"
    else:
        term_structure_regime = "contango" if sigma1 < sigma2 else "backwardation"
    expected_move_near_pct = float(sigma1 * np.sqrt(T1) * 100)
    expected_move_far_pct = float(sigma2 * np.sqrt(T2) * 100)

    return ForwardVolResult(
        sigma_near=sigma1,
        sigma_far=sigma2,
        forward_vol=sigma_f,
        term_structure_regime=term_structure_regime,
        low_confidence=low_confidence,
        T_near_years=T1,
        T_far_years=T2,
        expected_move_near_pct=expected_move_near_pct,
        expected_move_far_pct=expected_move_far_pct,
    )
