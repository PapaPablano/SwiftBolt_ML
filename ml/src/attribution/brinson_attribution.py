"""Brinson-Hood-Beebower performance attribution."""

import logging
from dataclasses import dataclass
from typing import Dict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """Attribution breakdown."""
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_active_return: float


class BrinsonAttribution:
    """Brinson-Hood-Beebower attribution analysis."""
    
    def __init__(self):
        logger.info("BrinsonAttribution initialized")
    
    def analyze(self, portfolio_weights: Dict[str, float], 
                benchmark_weights: Dict[str, float],
                portfolio_returns: Dict[str, float],
                benchmark_returns: Dict[str, float]) -> AttributionResult:
        """Perform Brinson attribution.
        
        Args:
            portfolio_weights: {asset: weight}
            benchmark_weights: {asset: weight}
            portfolio_returns: {asset: return}
            benchmark_returns: {asset: return}
        
        Returns:
            AttributionResult
        """
        # Convert to DataFrames
        assets = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
        
        data = []
        for asset in assets:
            pw = portfolio_weights.get(asset, 0)
            bw = benchmark_weights.get(asset, 0)
            pr = portfolio_returns.get(asset, 0)
            br = benchmark_returns.get(asset, 0)
            data.append({'asset': asset, 'pw': pw, 'bw': bw, 'pr': pr, 'br': br})
        
        df = pd.DataFrame(data)
        
        # Brinson attribution components
        # Allocation effect: (Wp - Wb) * (Rb - R_benchmark)
        R_benchmark = (df['bw'] * df['br']).sum()
        df['allocation'] = (df['pw'] - df['bw']) * (df['br'] - R_benchmark)
        
        # Selection effect: Wb * (Rp - Rb)
        df['selection'] = df['bw'] * (df['pr'] - df['br'])
        
        # Interaction effect: (Wp - Wb) * (Rp - Rb)
        df['interaction'] = (df['pw'] - df['bw']) * (df['pr'] - df['br'])
        
        # Total effects
        allocation_effect = df['allocation'].sum()
        selection_effect = df['selection'].sum()
        interaction_effect = df['interaction'].sum()
        
        # Total active return
        R_portfolio = (df['pw'] * df['pr']).sum()
        total_active_return = R_portfolio - R_benchmark
        
        return AttributionResult(
            allocation_effect=float(allocation_effect),
            selection_effect=float(selection_effect),
            interaction_effect=float(interaction_effect),
            total_active_return=float(total_active_return)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Brinson Attribution - Self Test")
    print("=" * 70)
    
    # Example portfolio
    portfolio_weights = {'AAPL': 0.3, 'GOOGL': 0.3, 'MSFT': 0.4}
    benchmark_weights = {'AAPL': 0.25, 'GOOGL': 0.25, 'MSFT': 0.5}
    portfolio_returns = {'AAPL': 0.10, 'GOOGL': 0.15, 'MSFT': 0.08}
    benchmark_returns = {'AAPL': 0.09, 'GOOGL': 0.12, 'MSFT': 0.10}
    
    brinson = BrinsonAttribution()
    result = brinson.analyze(portfolio_weights, benchmark_weights, 
                            portfolio_returns, benchmark_returns)
    
    print(f"\nAllocation Effect: {result.allocation_effect:.4f} ({result.allocation_effect*100:.2f}%)")
    print(f"Selection Effect: {result.selection_effect:.4f} ({result.selection_effect*100:.2f}%)")
    print(f"Interaction Effect: {result.interaction_effect:.4f} ({result.interaction_effect*100:.2f}%)")
    print(f"Total Active Return: {result.total_active_return:.4f} ({result.total_active_return*100:.2f}%)")
    
    print("\n✅ Brinson attribution test complete!")
