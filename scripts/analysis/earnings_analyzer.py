"""
Earnings IV Expansion/Crush Strategy Analyzer
=============================================

Detects and scores options based on proximity to earnings announcements
and implied volatility regime (expanding vs. contracting).
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import numpy as np


class EarningsIVAnalyzer:
    """
    Analyzes options in context of earnings announcements.
    """
    
    @staticmethod
    def calculate_earnings_impact_on_iv(
        current_iv: float,
        historical_iv: float,
        days_to_earnings: int,
        days_to_expiry: int,
        recent_earnings_dates: Optional[list] = None,
        post_earnings_iv_crush_percent: float = 0.35
    ) -> Dict:
        """
        Estimate IV expansion/contraction relative to earnings event.
        
        Typical IV behavior:
        - T-7 days: IV begins expanding
        - T-3 to T-0: IV peaks
        - T+1 day: IV crushes 20-40%
        """
        
        if days_to_earnings <= -1:
            iv_regime = 'post_earnings_crush'
            iv_mult = current_iv / (historical_iv + 1e-6)
            expansion_phase = 'none'
        elif days_to_earnings <= 0:
            iv_regime = 'earnings_day'
            iv_mult = current_iv / (historical_iv + 1e-6)
            expansion_phase = 'peak'
        elif days_to_earnings <= 3:
            iv_regime = 'pre_earnings_peak'
            iv_mult = current_iv / (historical_iv + 1e-6)
            expansion_phase = 'near_peak'
        elif days_to_earnings <= 7:
            iv_regime = 'pre_earnings_expansion'
            iv_mult = current_iv / (historical_iv + 1e-6)
            expansion_phase = 'mid_expansion'
        else:
            iv_regime = 'pre_earnings_slow'
            iv_mult = current_iv / (historical_iv + 1e-6)
            expansion_phase = 'early_expansion'
        
        post_earnings_iv = current_iv * (1.0 - post_earnings_iv_crush_percent)
        iv_crush_opportunity = current_iv - post_earnings_iv
        
        decay_before_earnings = days_to_earnings if days_to_earnings > 0 else 0
        decay_after_earnings = days_to_expiry - decay_before_earnings
        
        return {
            'current_iv': current_iv,
            'historical_iv': historical_iv,
            'iv_regime': iv_regime,
            'iv_multiplier': iv_mult,
            'iv_percentile': _estimate_iv_percentile(current_iv, historical_iv),
            'estimated_post_earnings_iv': post_earnings_iv,
            'iv_crush_opportunity': iv_crush_opportunity,
            'iv_crush_percent': post_earnings_iv_crush_percent * 100,
            'days_to_earnings': days_to_earnings,
            'days_to_expiry': days_to_expiry,
            'decay_days_before_earnings': decay_before_earnings,
            'decay_days_after_earnings': decay_after_earnings,
            'expansion_phase': expansion_phase,
        }
    
    @staticmethod
    def score_earnings_strategy(
        earnings_ Dict,
        side: str,
        expiration: str,
        underlying_price: float,
        strike: float,
        strategy_type: str = 'auto'
    ) -> float:
        """
        Score option based on earnings strategy alignment.
        """
        
        iv_mult = earnings_data['iv_multiplier']
        crush = earnings_data['iv_crush_opportunity']
        dte = earnings_data['days_to_earnings']
        days_to_exp = earnings_data['days_to_expiry']
        
        if strategy_type == 'auto':
            if 1 <= dte <= 5 and days_to_exp >= 1:
                strategy_type = 'sell_premium'
            elif dte > 14 and iv_mult < 1.0:
                strategy_type = 'buy_straddle'
            else:
                strategy_type = 'neutral'
        
        if strategy_type == 'sell_premium':
            if 1 <= dte <= 5:
                return min(crush / (iv_mult + 1e-6), 1.0) * 0.95
            elif dte == 0:
                return 0.92
            else:
                return 0.5
        
        elif strategy_type == 'buy_straddle':
            if dte > 14 and iv_mult < 1.0:
                undervalue = 1.0 - iv_mult
                return min(undervalue * 1.2, 1.0) * 0.90
            else:
                return 0.5
        
        else:
            return 0.7
    
    @staticmethod
    def earnings_opportunity_score(earnings_ Dict, side: str, bid: float, ask: float) -> float:
        """
        Composite opportunity score for earnings-aware trading.
        """
        mid_price = (bid + ask) / 2.0
        crush = earnings_data['iv_crush_opportunity']
        dte = earnings_data['days_to_earnings']
        iv_mult = earnings_data['iv_multiplier']
        
        if dte <= 0:
            return 0.5
        elif 1 <= dte <= 5:
            crush_value = min(crush / (mid_price + 1e-6), 1.0)
            return min(crush_value * 1.1, 1.0)
        elif 6 <= dte <= 14:
            return 0.75
        else:
            if iv_mult < 0.9:
                return 0.85
            else:
                return 0.6


def _estimate_iv_percentile(current_iv: float, historical_iv: float) -> float:
    """
    Rough estimate of IV percentile.
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
