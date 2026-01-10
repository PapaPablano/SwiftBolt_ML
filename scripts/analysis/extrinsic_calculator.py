"""
Extrinsic vs. Intrinsic Value Ratio Analyzer
============================================

Decomposes option price into intrinsic (stock parity) and extrinsic (time value)
to identify whether an option is "time value rich" or "intrinsic rich".
"""

from typing import Dict
import numpy as np


class ExtrinsicIntrinsicCalculator:
    """
    Analyzes the decomposition of option price into intrinsic and extrinsic components.
    """
    
    @staticmethod
    def calculate_extrinsic_intrinsic_ratio(
        strike: float,
        underlying_price: float,
        side: str,
        bid: float,
        ask: float,
        days_to_expiry: int
    ) -> Dict:
        """
        Decompose option price into intrinsic and extrinsic value.
        """
        mid_price = (bid + ask) / 2.0
        
        if side == 'call':
            intrinsic = max(0, underlying_price - strike)
        elif side == 'put':
            intrinsic = max(0, strike - underlying_price)
        else:
            raise ValueError(f"Invalid side: {side}")
        
        extrinsic = max(0, mid_price - intrinsic)
        
        total_value = mid_price
        extrinsic_ratio = extrinsic / (total_value + 1e-6)
        intrinsic_ratio = intrinsic / (total_value + 1e-6)
        
        if days_to_expiry > 0:
            daily_extrinsic_decay = extrinsic / days_to_expiry
            daily_intrinsic_decay = intrinsic / days_to_expiry
        else:
            daily_extrinsic_decay = extrinsic
            daily_intrinsic_decay = intrinsic
        
        if extrinsic_ratio > 0.75:
            character = 'time_value_rich'
            description = 'Primarily time/vol premium; benefits from decay'
        elif extrinsic_ratio < 0.25:
            character = 'intrinsic_rich'
            description = 'Deep ITM; behaves like stock; limited leverage'
        else:
            character = 'balanced'
            description = 'Mixed; suitable for directional + decay strategies'
        
        moneyness = (strike - underlying_price) / underlying_price
        if side == 'call':
            if moneyness < -0.05:
                moneyness_type = 'ITM'
            elif -0.05 <= moneyness <= 0.05:
                moneyness_type = 'ATM'
            else:
                moneyness_type = 'OTM'
        else:
            if moneyness > 0.05:
                moneyness_type = 'ITM'
            elif -0.05 <= moneyness <= 0.05:
                moneyness_type = 'ATM'
            else:
                moneyness_type = 'OTM'
        
        return {
            'intrinsic_value': intrinsic,
            'extrinsic_value': extrinsic,
            'total_option_price': mid_price,
            'extrinsic_ratio': extrinsic_ratio,
            'intrinsic_ratio': intrinsic_ratio,
            'character': character,
            'character_description': description,
            'moneyness_type': moneyness_type,
            'daily_extrinsic_decay': daily_extrinsic_decay,
            'daily_intrinsic_decay': daily_intrinsic_decay,
            'days_to_expiry': days_to_expiry,
            'bid_ask_spread': ask - bid
        }
    
    @staticmethod
    def score_extrinsic_richness(
        extrinsic_ Dict,
        implied_vol: float,
        historical_vol: float,
        strategy_type: str = 'auto'
    ) -> float:
        """
        Score option based on extrinsic value saturation and strategy fit.
        """
        ratio = extrinsic_data['extrinsic_ratio']
        decay = extrinsic_data['daily_extrinsic_decay']
        iv_rank = implied_vol / (historical_vol + 1e-6)
        
        if strategy_type == 'sell_premium':
            extrinsic_score = min(ratio / 0.75, 1.0)
            iv_score = min(iv_rank / 1.3, 1.0)
            return (extrinsic_score * 0.6) + (iv_score * 0.4)
        
        elif strategy_type == 'buy_long':
            if ratio < 0.4:
                return 0.85
            elif ratio < 0.6:
                return 0.75
            else:
                return 0.5
        
        elif strategy_type == 'buy_straddle':
            if 0.4 <= ratio <= 0.7:
                return 0.90
            else:
                return 0.6
        
        elif strategy_type == 'auto':
            if iv_rank > 1.3 and ratio > 0.7:
                return 0.85
            elif ratio < 0.3:
                return 0.65
            else:
                return 0.75
        
        else:
            return 0.7
