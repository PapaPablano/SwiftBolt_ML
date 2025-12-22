"""
Put-Call Ratio (PCR) Sentiment Analyzer
======================================

Analyzes put-call ratio to gauge market sentiment and identify contrarian opportunities.
"""

from typing import Dict
import pandas as pd
import numpy as np


class PutCallRatioAnalyzer:
    """
    Calculates and scores put-call ratio for market sentiment analysis.
    """
    
    @staticmethod
    def analyze_put_call_ratio(options_df: pd.DataFrame) -> Dict:
        """
        Calculate multiple put-call ratio variants.
        """
        
        calls = options_df[options_df['side'] == 'call']
        puts = options_df[options_df['side'] == 'put']
        
        call_volume = calls['volume'].sum() if calls['volume'].sum() > 0 else 1e-6
        call_oi = calls['openInterest'].sum() if calls['openInterest'].sum() > 0 else 1e-6
        
        put_volume = puts['volume'].sum() if len(puts) > 0 else 0
        put_oi = puts['openInterest'].sum() if len(puts) > 0 else 0
        
        pcr_volume = put_volume / call_volume if call_volume > 0 else 0
        pcr_open_interest = put_oi / call_oi
        
        put_notional = (puts['strike'] * puts['openInterest']).sum() if len(puts) > 0 else 0
        call_notional = (calls['strike'] * calls['openInterest']).sum() if len(calls) > 0 else 1e-6
        pcr_weighted = put_notional / call_notional
        
        pcr_composite = (pcr_open_interest * 0.7) + (pcr_volume * 0.2) + (pcr_weighted * 0.1)
        
        if pcr_composite > 1.3:
            sentiment = 'extremely_bearish'
            signal = 'contrarian_bullish'
        elif pcr_composite > 1.1:
            sentiment = 'bearish'
            signal = 'slight_bullish'
        elif pcr_composite > 0.9:
            sentiment = 'slightly_bearish'
            signal = 'neutral'
        elif pcr_composite > 0.8:
            sentiment = 'slightly_bullish'
            signal = 'neutral'
        elif pcr_composite > 0.7:
            sentiment = 'bullish'
            signal = 'slight_bearish'
        else:
            sentiment = 'extremely_bullish'
            signal = 'contrarian_bearish'
        
        return {
            'pcr_volume': pcr_volume,
            'pcr_open_interest': pcr_open_interest,
            'pcr_weighted': pcr_weighted,
            'pcr_composite': pcr_composite,
            'sentiment': sentiment,
            'contrarian_signal': signal,
            'put_volume': put_volume,
            'call_volume': call_volume,
            'put_oi': put_oi,
            'call_oi': call_oi,
            'extreme_ratio': 'yes' if pcr_composite > 1.3 or pcr_composite < 0.7 else 'no'
        }
    
    @staticmethod
    def score_pcr_opportunity(
        pcr_ Dict,
        side: str,
        use_contrarian: bool = True
    ) -> float:
        """
        Score option based on put-call ratio opportunity.
        """
        pcr = pcr_data['pcr_composite']
        
        if use_contrarian:
            if side == 'call':
                if pcr > 1.3:
                    return 0.92
                elif pcr > 1.1:
                    return 0.80
                elif pcr < 0.7:
                    return 0.45
                elif pcr < 0.85:
                    return 0.55
                else:
                    return 0.70
            
            elif side == 'put':
                if pcr < 0.7:
                    return 0.92
                elif pcr < 0.85:
                    return 0.80
                elif pcr > 1.3:
                    return 0.45
                elif pcr > 1.15:
                    return 0.55
                else:
                    return 0.70
        else:
            if side == 'call':
                return 0.75 if pcr < 0.9 else 0.65
            else:
                return 0.75 if pcr > 1.0 else 0.65
    
    @staticmethod
    def get_pcr_strength_signal(pcr_composite: float) -> Dict:
        """
        Provide additional context on PCR strength and reliability.
        """
        if pcr_composite > 1.5:
            strength = 'extreme'
            reliability = 'high'
            signal_type = 'potential_capitulation'
        elif pcr_composite > 1.2:
            strength = 'strong'
            reliability = 'moderate'
            signal_type = 'hedging_active'
        elif pcr_composite > 1.0:
            strength = 'moderate'
            reliability = 'moderate'
            signal_type = 'slightly_defensive'
        elif pcr_composite > 0.8:
            strength = 'weak'
            reliability = 'low'
            signal_type = 'neutral'
        elif pcr_composite > 0.6:
            strength = 'moderate'
            reliability = 'moderate'
            signal_type = 'slightly_aggressive'
        elif pcr_composite > 0.5:
            strength = 'strong'
            reliability = 'moderate'
            signal_type = 'aggressive_positioning'
        else:
            strength = 'extreme'
            reliability = 'high'
            signal_type = 'potential_fomo'
        
        return {
            'pcr_strength': strength,
            'signal_reliability': reliability,
            'signal_interpretation': signal_type
        }
