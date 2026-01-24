"""Liquidity analysis for options contracts."""

import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class LiquidityScore:
    """Liquidity score metrics."""
    score: float  # 0-100
    bid_ask_spread_pct: float
    volume_score: float
    oi_score: float
    rating: str  # Excellent, Good, Fair, Poor


class LiquidityAnalyzer:
    """Analyze options liquidity."""
    
    def __init__(self, chain_data: pd.DataFrame):
        self.chain = chain_data
        logger.info(f"LiquidityAnalyzer initialized")
    
    def analyze(self, strike: float, option_type: str) -> LiquidityScore:
        """Analyze liquidity for specific contract."""
        contract = self.chain[(self.chain['strike'] == strike) & (self.chain['type'] == option_type)]
        
        if len(contract) == 0:
            return LiquidityScore(0, 0, 0, 0, "Poor")
        
        contract = contract.iloc[0]
        
        # Bid-ask spread
        mid = (contract['bid'] + contract['ask']) / 2
        spread_pct = (contract['ask'] - contract['bid']) / mid if mid > 0 else 1
        spread_score = max(0, 100 * (1 - spread_pct / 0.10))  # 10% spread = 0
        
        # Volume score (relative to chain)
        vol_percentile = (self.chain['volume'] < contract['volume']).mean() * 100
        
        # OI score
        oi_percentile = (self.chain['oi'] < contract['oi']).mean() * 100
        
        # Combined score
        score = (spread_score * 0.4 + vol_percentile * 0.3 + oi_percentile * 0.3)
        
        # Rating
        if score >= 80:
            rating = "Excellent"
        elif score >= 60:
            rating = "Good"
        elif score >= 40:
            rating = "Fair"
        else:
            rating = "Poor"
        
        return LiquidityScore(
            score=float(score),
            bid_ask_spread_pct=float(spread_pct),
            volume_score=float(vol_percentile),
            oi_score=float(oi_percentile),
            rating=rating
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("✅ Liquidity analyzer ready")
