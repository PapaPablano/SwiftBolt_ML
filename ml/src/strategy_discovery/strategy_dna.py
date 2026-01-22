"""Strategy DNA encoding for genetic algorithms."""

import logging
from dataclasses import dataclass
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StrategyGene:
    """Single strategy gene."""
    name: str
    value: float
    min_val: float
    max_val: float


class StrategyDNA:
    """Encode trading strategy as DNA for genetic evolution."""
    
    GENE_TEMPLATES = {
        'lookback_period': (5, 200),
        'entry_threshold': (-2.0, 2.0),
        'exit_threshold': (-2.0, 2.0),
        'stop_loss_pct': (0.01, 0.20),
        'take_profit_pct': (0.01, 0.50),
        'position_size': (0.01, 0.20),
        'rsi_threshold': (20, 80),
        'volatility_filter': (0.10, 1.0)
    }
    
    def __init__(self, genes: List[str] = None):
        """Initialize DNA with specified genes."""
        self.genes = genes or ['lookback_period', 'entry_threshold', 'position_size']
        self.chromosome = self._initialize_chromosome()
        logger.debug(f"StrategyDNA created with {len(self.genes)} genes")
    
    def _initialize_chromosome(self) -> np.ndarray:
        """Initialize random chromosome."""
        return np.array([
            np.random.uniform(self.GENE_TEMPLATES[gene][0], self.GENE_TEMPLATES[gene][1])
            for gene in self.genes
        ])
    
    def decode(self) -> Dict[str, float]:
        """Decode chromosome to strategy parameters."""
        return {gene: value for gene, value in zip(self.genes, self.chromosome)}
    
    def encode(self, params: Dict[str, float]):
        """Encode strategy parameters to chromosome."""
        self.chromosome = np.array([params[gene] for gene in self.genes])
    
    def get_bounds(self) -> List[tuple]:
        """Get gene bounds for optimization."""
        return [self.GENE_TEMPLATES[gene] for gene in self.genes]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dna = StrategyDNA(['lookback_period', 'entry_threshold', 'position_size'])
    params = dna.decode()
    print(f"Decoded params: {params}")
    print("✅ Strategy DNA ready")
