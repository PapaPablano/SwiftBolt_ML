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
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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
