"""
Earnings IV Expansion/Crush Strategy Analyzer
=============================================

Detects and scores options based on proximity to earnings announcements
and implied volatility regime (expanding vs. contracting).

P0 Module for Enhanced Options Ranker.

Typical IV behavior around earnings:
- T-7 days: IV begins expanding
- T-3 to T-0: IV peaks
- T+1 day: IV crushes 20-40%

Bracketing expiries: E1 = last before earnings, E2 = first after.
Variance subtraction: v_event = (T_E2 - T_E1) * sigma_f^2 - N_base * v_base.
Event 1-σ move: S * sqrt(v_event).
Time convention: ACT/365 for T in years (documented in docstrings).
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Time convention: ACT/365 for T in years
ACT_365 = 365.0


@dataclass
class EarningsJumpResult:
    """Result of earnings jump isolation via bracketing expiries."""

    event_variance: float  # Isolated event variance
    event_1sigma_move: float  # S * sqrt(v_event)
    sigma_f: float  # Forward vol in (T_E1, T_E2)
    T_E1: float  # T of E1 in years
    T_E2: float  # T of E2 in years
    used_bracketing: bool  # True if E1/E2 found; False if heuristic fallback


class EarningsIVAnalyzer:
    """
    Analyzes options in context of earnings announcements.

    Identifies:
    - IV expansion opportunities (buy before earnings)
    - IV crush opportunities (sell before earnings)
    - Post-earnings value plays
    """

    @staticmethod
    def calculate_earnings_impact_on_iv(
        current_iv: float,
        historical_iv: float,
        days_to_earnings: int,
        days_to_expiry: int,
        recent_earnings_dates: Optional[list] = None,
        post_earnings_iv_crush_percent: float = 0.35,
    ) -> Dict:
        """
        Estimate IV expansion/contraction relative to earnings event.

        Args:
            current_iv: Current implied volatility
            historical_iv: Historical (realized) volatility
            days_to_earnings: Days until earnings announcement
            days_to_expiry: Days until option expiration
            recent_earnings_dates: List of recent earnings dates
            post_earnings_iv_crush_percent: Expected IV crush after earnings

        Returns:
            Dict with earnings IV analysis
        """
        # Determine IV regime based on proximity to earnings
        if days_to_earnings <= -1:
            iv_regime = "post_earnings_crush"
            expansion_phase = "none"
        elif days_to_earnings <= 0:
            iv_regime = "earnings_day"
            expansion_phase = "peak"
        elif days_to_earnings <= 3:
            iv_regime = "pre_earnings_peak"
            expansion_phase = "near_peak"
        elif days_to_earnings <= 7:
            iv_regime = "pre_earnings_expansion"
            expansion_phase = "mid_expansion"
        else:
            iv_regime = "pre_earnings_slow"
            expansion_phase = "early_expansion"

        iv_mult = current_iv / (historical_iv + 1e-6)

        # Estimate post-earnings IV
        post_earnings_iv = current_iv * (1.0 - post_earnings_iv_crush_percent)
        iv_crush_opportunity = current_iv - post_earnings_iv

        # Time decay distribution
        decay_before_earnings = max(0, days_to_earnings)
        decay_after_earnings = days_to_expiry - decay_before_earnings

        return {
            "current_iv": current_iv,
            "historical_iv": historical_iv,
            "iv_regime": iv_regime,
            "iv_multiplier": iv_mult,
            "iv_percentile": _estimate_iv_percentile(current_iv, historical_iv),
            "estimated_post_earnings_iv": post_earnings_iv,
            "iv_crush_opportunity": iv_crush_opportunity,
            "iv_crush_percent": post_earnings_iv_crush_percent * 100,
            "days_to_earnings": days_to_earnings,
            "days_to_expiry": days_to_expiry,
            "decay_days_before_earnings": decay_before_earnings,
            "decay_days_after_earnings": decay_after_earnings,
            "expansion_phase": expansion_phase,
        }

    @staticmethod
    def score_earnings_strategy(
        earnings_data: Dict,
        side: str,
        expiration: str,
        underlying_price: float,
        strike: float,
        strategy_type: str = "auto",
    ) -> float:
        """
        Score option based on earnings strategy alignment.

        Strategy types:
        - 'sell_premium': Sell options before earnings to capture IV crush
        - 'buy_straddle': Buy options when IV is low before expansion
        - 'auto': Automatically select best strategy

        Args:
            earnings_data: Dict from calculate_earnings_impact_on_iv()
            side: 'call' or 'put'
            expiration: Expiration date string
            underlying_price: Current stock price
            strike: Option strike price
            strategy_type: Strategy to score for

        Returns:
            Score from 0-1
        """
        iv_mult = earnings_data["iv_multiplier"]
        crush = earnings_data["iv_crush_opportunity"]
        dte = earnings_data["days_to_earnings"]
        days_to_exp = earnings_data["days_to_expiry"]

        # Auto-select strategy based on conditions
        if strategy_type == "auto":
            if 1 <= dte <= 5 and days_to_exp >= 1:
                strategy_type = "sell_premium"
            elif dte > 14 and iv_mult < 1.0:
                strategy_type = "buy_straddle"
            else:
                strategy_type = "neutral"

        # Score based on strategy
        if strategy_type == "sell_premium":
            # Best when IV is elevated and earnings imminent
            if 1 <= dte <= 5:
                return min(crush / (iv_mult + 1e-6), 1.0) * 0.95
            elif dte == 0:
                return 0.92
            else:
                return 0.5

        elif strategy_type == "buy_straddle":
            # Best when IV is low with time for expansion
            if dte > 14 and iv_mult < 1.0:
                undervalue = 1.0 - iv_mult
                return min(undervalue * 1.2, 1.0) * 0.90
            else:
                return 0.5

        else:  # neutral
            return 0.7

    @staticmethod
    def earnings_opportunity_score(earnings_data: Dict, side: str, bid: float, ask: float) -> float:
        """
        Composite opportunity score for earnings-aware trading.

        Args:
            earnings_data: Dict from calculate_earnings_impact_on_iv()
            side: 'call' or 'put'
            bid: Bid price
            ask: Ask price

        Returns:
            Score from 0-1
        """
        mid_price = (bid + ask) / 2.0
        crush = earnings_data["iv_crush_opportunity"]
        dte = earnings_data["days_to_earnings"]
        iv_mult = earnings_data["iv_multiplier"]

        if dte <= 0:
            return 0.5  # Post-earnings, neutral
        elif 1 <= dte <= 5:
            # Prime IV crush opportunity
            crush_value = min(crush / (mid_price + 1e-6), 1.0)
            return min(crush_value * 1.1, 1.0)
        elif 6 <= dte <= 14:
            return 0.75  # Moderate opportunity
        else:
            # Far from earnings - look for undervalued IV
            if iv_mult < 0.9:
                return 0.85
            else:
                return 0.6


def isolate_earnings_jump(
    options_df: pd.DataFrame,
    spot: float,
    earnings_date: datetime | str,
    realized_vol: float | None = None,
    reference_ts: float | None = None,
) -> EarningsJumpResult | None:
    """
    Isolate earnings jump variance using bracketing expiries.

    E1 = last expiry before earnings
    E2 = first expiry after earnings
    Forward vol sigma_f in (T_E1, T_E2) from ATM IV curve.
    Baseline daily variance v_base from realized_vol^2 / 252 (or heuristic).
    Event variance: v_event = (T_E2 - T_E1) * sigma_f^2 - N_base * v_base
    Event 1-σ move: S * sqrt(v_event)

    Time convention: ACT/365 for T in years.

    Args:
        options_df: Options chain with expiration, strike, impliedVolatility/iv
        spot: Underlying price
        earnings_date: Earnings announcement date (datetime or YYYY-MM-DD)
        realized_vol: Annualized realized vol for baseline variance
        reference_ts: Unix seconds for T; defaults to now

    Returns:
        EarningsJumpResult or None if bracketing not available
    """
    import time as _time

    if options_df.empty or "expiration" not in options_df.columns:
        return None

    ref = reference_ts if reference_ts is not None else _time.time()

    if isinstance(earnings_date, str):
        try:
            earn_dt = datetime.strptime(earnings_date[:10], "%Y-%m-%d")
        except ValueError:
            return None
    else:
        earn_dt = earnings_date
    earn_ts = earn_dt.timestamp()

    expiries: List[tuple[float, Any]] = []
    for exp_val in options_df["expiration"].unique():
        if pd.isna(exp_val):
            continue
        try:
            if isinstance(exp_val, (int, float)) and exp_val > 1e9:
                ts = float(exp_val)
            else:
                ts = pd.Timestamp(str(exp_val)).timestamp()
            expiries.append((ts, exp_val))
        except Exception:
            continue

    if len(expiries) < 2:
        return None

    expiries.sort(key=lambda x: x[0])

    E1: tuple[float, Any] | None = None
    E2: tuple[float, Any] | None = None
    for ts, val in expiries:
        if ts < earn_ts:
            E1 = (ts, val)
        elif ts >= earn_ts and E2 is None:
            E2 = (ts, val)
            break

    if E1 is None or E2 is None:
        return None

    ts1, _ = E1
    ts2, _ = E2

    T1 = max(0, (ts1 - ref) / 86400) / ACT_365
    T2 = max(0, (ts2 - ref) / 86400) / ACT_365
    if T2 <= T1:
        return None

    grp1 = options_df[options_df["expiration"] == E1[1]]
    grp2 = options_df[options_df["expiration"] == E2[1]]
    iv_col = "iv" if "iv" in options_df.columns else "impliedVolatility"
    if iv_col not in options_df.columns:
        iv_col = "implied_vol"
    if iv_col not in options_df.columns:
        return None

    atm_strike_1 = min(grp1["strike"].unique(), key=lambda k: abs(float(k) - spot))
    atm_strike_2 = min(grp2["strike"].unique(), key=lambda k: abs(float(k) - spot))
    iv1 = grp1[grp1["strike"] == atm_strike_1][iv_col].mean()
    iv2 = grp2[grp2["strike"] == atm_strike_2][iv_col].mean()
    if np.isnan(iv1) or np.isnan(iv2) or iv1 <= 0 or iv2 <= 0:
        return None

    v1 = T1 * (iv1 ** 2)
    v2 = T2 * (iv2 ** 2)
    numerator = v2 - v1
    if numerator < 0:
        numerator = 0.0
    sigma_f = float(np.sqrt(numerator / (T2 - T1)))

    N_base = (T2 - T1) * ACT_365
    if realized_vol is not None and np.isfinite(realized_vol) and realized_vol > 0:
        v_base = (realized_vol ** 2) / 252
    else:
        v_base = (sigma_f ** 2) / 30

    total_var = (T2 - T1) * (sigma_f ** 2)
    v_event = max(0.0, total_var - N_base * v_base)

    event_1sigma = spot * np.sqrt(v_event) if v_event > 0 else 0.0

    return EarningsJumpResult(
        event_variance=v_event,
        event_1sigma_move=float(event_1sigma),
        sigma_f=sigma_f,
        T_E1=T1,
        T_E2=T2,
        used_bracketing=True,
    )


def _estimate_iv_percentile(current_iv: float, historical_iv: float) -> float:
    """
    Rough estimate of IV percentile based on IV/HV ratio.

    Args:
        current_iv: Current implied volatility
        historical_iv: Historical volatility

    Returns:
        Estimated IV percentile (0-1)
    """
    iv_ratio = current_iv / (historical_iv + 1e-6)
    if iv_ratio < 0.5:
        return 0.05
    elif iv_ratio < 0.8:
        return 0.25
    elif iv_ratio < 1.0:
        return 0.50
    elif iv_ratio < 1.3:
        return 0.75
    else:
        return 0.95
