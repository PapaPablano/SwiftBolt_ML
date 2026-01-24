"""Options chain analysis and metrics calculation.

Analyzes full options chains to extract market insights.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ChainAnalysis:
    """Options chain analysis results."""
    max_pain: float
    put_call_ratio: float
    total_call_oi: int
    total_put_oi: int
    call_volume: int
    put_volume: int
    atm_iv: float
    iv_skew: float
    
    def summary(self) -> str:
        return (
            f"Max Pain: ${self.max_pain:.2f}\n"
            f"Put/Call Ratio: {self.put_call_ratio:.2f}\n"
            f"ATM IV: {self.atm_iv:.2%}"
        )


class OptionsChain:
    """Options chain analyzer."""
    
    def __init__(self, chain_data: pd.DataFrame):
        """Initialize with chain data.
        
        Args:
            chain_data: DataFrame with columns: strike, type, oi, volume, iv, bid, ask
        """
        self.chain = chain_data
        logger.info(f"OptionsChain initialized: {len(chain_data)} contracts")
    
    def calculate_max_pain(self) -> float:
        """Calculate max pain strike."""
        calls = self.chain[self.chain['type'] == 'call']
        puts = self.chain[self.chain['type'] == 'put']
        
        strikes = sorted(self.chain['strike'].unique())
        pain = []
        
        for strike in strikes:
            call_pain = calls[calls['strike'] < strike]['oi'].sum() * (strike - calls[calls['strike'] < strike]['strike']).sum()
            put_pain = puts[puts['strike'] > strike]['oi'].sum() * (puts[puts['strike'] > strike]['strike'] - strike).sum()
            pain.append(call_pain + put_pain)
        
        return strikes[np.argmin(pain)]
    
    def calculate_put_call_ratio(self) -> float:
        """Calculate put/call ratio."""
        put_oi = self.chain[self.chain['type'] == 'put']['oi'].sum()
        call_oi = self.chain[self.chain['type'] == 'call']['oi'].sum()
        return put_oi / call_oi if call_oi > 0 else 0
    
    def analyze(self, underlying_price: float) -> ChainAnalysis:
        """Full chain analysis."""
        calls = self.chain[self.chain['type'] == 'call']
        puts = self.chain[self.chain['type'] == 'put']
        
        # ATM contracts
        atm_calls = calls.iloc[(calls['strike'] - underlying_price).abs().argsort()[:1]]
        atm_puts = puts.iloc[(puts['strike'] - underlying_price).abs().argsort()[:1]]
        atm_iv = (atm_calls['iv'].mean() + atm_puts['iv'].mean()) / 2
        
        # IV skew
        otm_calls = calls[calls['strike'] > underlying_price * 1.05]
        otm_puts = puts[puts['strike'] < underlying_price * 0.95]
        iv_skew = otm_puts['iv'].mean() - otm_calls['iv'].mean() if len(otm_puts) > 0 and len(otm_calls) > 0 else 0
        
        return ChainAnalysis(
            max_pain=self.calculate_max_pain(),
            put_call_ratio=self.calculate_put_call_ratio(),
            total_call_oi=int(calls['oi'].sum()),
            total_put_oi=int(puts['oi'].sum()),
            call_volume=int(calls['volume'].sum()),
            put_volume=int(puts['volume'].sum()),
            atm_iv=float(atm_iv),
            iv_skew=float(iv_skew)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Options Chain - Self Test")
    print("=" * 70)
    
    # Generate synthetic chain
    np.random.seed(42)
    strikes = np.arange(90, 111, 5)
    
    chain_data = []
    for strike in strikes:
        chain_data.append({
            'strike': strike,
            'type': 'call',
            'oi': np.random.randint(100, 1000),
            'volume': np.random.randint(10, 100),
            'iv': 0.25 + np.random.randn() * 0.05,
            'bid': max(0.1, np.random.rand() * 5),
            'ask': max(0.2, np.random.rand() * 5 + 0.1)
        })
        chain_data.append({
            'strike': strike,
            'type': 'put',
            'oi': np.random.randint(100, 1000),
            'volume': np.random.randint(10, 100),
            'iv': 0.28 + np.random.randn() * 0.05,
            'bid': max(0.1, np.random.rand() * 5),
            'ask': max(0.2, np.random.rand() * 5 + 0.1)
        })
    
    chain_df = pd.DataFrame(chain_data)
    
    chain = OptionsChain(chain_df)
    analysis = chain.analyze(underlying_price=100)
    
    print(f"\n{analysis.summary()}")
    print("\n✅ Options chain test complete!")
