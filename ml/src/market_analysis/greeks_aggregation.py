"""Greeks aggregation across options chains."""

import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AggregatedGreeks:
    """Aggregated Greeks metrics."""
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    net_delta_exposure: float
    gamma_weighted_vega: float


class GreeksAggregator:
    """Aggregate Greeks across options chain."""
    
    def __init__(self, chain_data: pd.DataFrame):
        """Initialize with chain data containing Greeks."""
        self.chain = chain_data
        logger.info(f"GreeksAggregator initialized: {len(chain_data)} contracts")
    
    def aggregate(self, positions: pd.DataFrame = None) -> AggregatedGreeks:
        """Aggregate Greeks, optionally weighted by positions."""
        if positions is not None:
            chain = self.chain.merge(positions, on=['strike', 'type'], how='left')
            chain['position'] = chain['position'].fillna(0)
        else:
            chain = self.chain.copy()
            chain['position'] = chain.get('oi', 1)
        
        # Weighted Greeks
        total_delta = (chain['delta'] * chain['position']).sum()
        total_gamma = (chain['gamma'] * chain['position']).sum()
        total_vega = (chain['vega'] * chain['position']).sum()
        total_theta = (chain['theta'] * chain['position']).sum()
        
        # Net exposure
        calls = chain[chain['type'] == 'call']
        puts = chain[chain['type'] == 'put']
        net_delta = (calls['delta'] * calls['position']).sum() - (puts['delta'] * puts['position']).sum()
        
        # Gamma-weighted vega
        gwv = (chain['gamma'] * chain['vega'] * chain['position']).sum()
        
        return AggregatedGreeks(
            total_delta=float(total_delta),
            total_gamma=float(total_gamma),
            total_vega=float(total_vega),
            total_theta=float(total_theta),
            net_delta_exposure=float(net_delta),
            gamma_weighted_vega=float(gwv)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("✅ Greeks aggregation ready")
