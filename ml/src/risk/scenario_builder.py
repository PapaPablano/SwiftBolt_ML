"""Scenario builder for creating custom stress test scenarios.

Build complex scenarios by combining multiple factors:
- Market moves
- Volatility changes
- Correlation shifts
- Interest rate changes

Usage:
    from src.risk.scenario_builder import ScenarioBuilder
    
    # Build scenario
    builder = ScenarioBuilder()
    builder.add_market_shock('SPY', -0.20)
    builder.add_volatility_spike(2.0)
    builder.add_correlation_shift(0.30)
    
    scenario = builder.build("Market Crash + Vol Spike")
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """Custom scenario definition.
    
    Attributes:
        name: Scenario name
        market_shocks: Price shocks by symbol
        volatility_multiplier: Volatility change multiplier
        correlation_adjustment: Correlation adjustment
        description: Scenario description
    """
    name: str
    market_shocks: Dict[str, float] = field(default_factory=dict)
    volatility_multiplier: float = 1.0
    correlation_adjustment: float = 0.0
    description: str = ""
    
    def summary(self) -> str:
        """Get scenario summary."""
        lines = [
            f"Scenario: {self.name}",
            f"Description: {self.description or 'Custom scenario'}",
            f"\nMarket Shocks:"
        ]
        
        for symbol, shock in self.market_shocks.items():
            lines.append(f"  {symbol}: {shock:+.2%}")
        
        lines.append(f"\nVolatility Multiplier: {self.volatility_multiplier:.2f}x")
        lines.append(f"Correlation Adjustment: {self.correlation_adjustment:+.2f}")
        
        return "\n".join(lines)


class ScenarioBuilder:
    """Builder for creating custom stress test scenarios."""
    
    def __init__(self):
        """Initialize scenario builder."""
        self.market_shocks: Dict[str, float] = {}
        self.volatility_multiplier: float = 1.0
        self.correlation_adjustment: float = 0.0
        self.description: str = ""
        
        logger.debug("ScenarioBuilder initialized")
    
    def add_market_shock(
        self,
        symbol: str,
        shock_pct: float
    ) -> 'ScenarioBuilder':
        """Add market shock for a symbol.
        
        Args:
            symbol: Asset symbol
            shock_pct: Price change (e.g., -0.20 for -20%)
        
        Returns:
            Self for chaining
        """
        self.market_shocks[symbol] = shock_pct
        return self
    
    def add_broad_market_shock(
        self,
        shock_pct: float,
        indices: Optional[List[str]] = None
    ) -> 'ScenarioBuilder':
        """Add broad market shock across multiple indices.
        
        Args:
            shock_pct: Price change
            indices: List of index symbols (defaults to major indices)
        
        Returns:
            Self for chaining
        """
        if indices is None:
            indices = ['SPY', 'QQQ', 'IWM', 'DIA']
        
        for symbol in indices:
            self.market_shocks[symbol] = shock_pct
        
        return self
    
    def add_volatility_spike(
        self,
        multiplier: float
    ) -> 'ScenarioBuilder':
        """Add volatility spike.
        
        Args:
            multiplier: Volatility multiplier (e.g., 2.0 for 2x increase)
        
        Returns:
            Self for chaining
        """
        self.volatility_multiplier = multiplier
        return self
    
    def add_correlation_shift(
        self,
        adjustment: float
    ) -> 'ScenarioBuilder':
        """Add correlation adjustment.
        
        Args:
            adjustment: Correlation adjustment (e.g., 0.30 for +30% increase)
        
        Returns:
            Self for chaining
        """
        self.correlation_adjustment = adjustment
        return self
    
    def set_description(self, description: str) -> 'ScenarioBuilder':
        """Set scenario description.
        
        Args:
            description: Scenario description
        
        Returns:
            Self for chaining
        """
        self.description = description
        return self
    
    def build(self, name: str) -> Scenario:
        """Build scenario.
        
        Args:
            name: Scenario name
        
        Returns:
            Scenario object
        """
        scenario = Scenario(
            name=name,
            market_shocks=self.market_shocks.copy(),
            volatility_multiplier=self.volatility_multiplier,
            correlation_adjustment=self.correlation_adjustment,
            description=self.description
        )
        
        logger.info(f"Built scenario: {name}")
        
        # Reset builder
        self.market_shocks = {}
        self.volatility_multiplier = 1.0
        self.correlation_adjustment = 0.0
        self.description = ""
        
        return scenario
    
    @staticmethod
    def create_recession_scenario() -> Scenario:
        """Create recession scenario.
        
        Returns:
            Scenario object
        """
        builder = ScenarioBuilder()
        return (builder
                .add_broad_market_shock(-0.25)
                .add_market_shock('TLT', 0.20)  # Flight to safety
                .add_market_shock('GLD', 0.10)
                .add_volatility_spike(2.5)
                .add_correlation_shift(0.40)
                .set_description("Recession scenario with flight to quality")
                .build("Recession"))
    
    @staticmethod
    def create_inflation_shock_scenario() -> Scenario:
        """Create inflation shock scenario.
        
        Returns:
            Scenario object
        """
        builder = ScenarioBuilder()
        return (builder
                .add_broad_market_shock(-0.15)
                .add_market_shock('TLT', -0.15)  # Bonds sell off
                .add_market_shock('TIP', 0.05)   # TIPS benefit
                .add_market_shock('GLD', 0.15)   # Gold benefits
                .add_volatility_spike(1.8)
                .set_description("Unexpected inflation spike")
                .build("Inflation Shock"))
    
    @staticmethod
    def create_liquidity_crisis_scenario() -> Scenario:
        """Create liquidity crisis scenario.
        
        Returns:
            Scenario object
        """
        builder = ScenarioBuilder()
        return (builder
                .add_broad_market_shock(-0.30)
                .add_volatility_spike(3.0)
                .add_correlation_shift(0.60)  # Everything sells off together
                .set_description("Liquidity crisis with forced selling")
                .build("Liquidity Crisis"))
    
    @staticmethod
    def create_geopolitical_crisis_scenario() -> Scenario:
        """Create geopolitical crisis scenario.
        
        Returns:
            Scenario object
        """
        builder = ScenarioBuilder()
        return (builder
                .add_broad_market_shock(-0.20)
                .add_market_shock('GLD', 0.20)  # Safe haven
                .add_market_shock('USO', 0.30)  # Oil spikes
                .add_volatility_spike(2.2)
                .set_description("Major geopolitical crisis")
                .build("Geopolitical Crisis"))


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Scenario Builder - Self Test")
    print("=" * 70)
    
    # Test 1: Custom scenario
    print("\n📊 Test 1: Custom Scenario")
    
    builder = ScenarioBuilder()
    scenario1 = (builder
                 .add_market_shock('SPY', -0.15)
                 .add_market_shock('QQQ', -0.20)
                 .add_market_shock('TLT', 0.10)
                 .add_volatility_spike(2.0)
                 .add_correlation_shift(0.25)
                 .set_description("Tech selloff with rotation to bonds")
                 .build("Tech Selloff"))
    
    print(f"\n{scenario1.summary()}")
    
    # Test 2: Predefined scenarios
    print("\n📊 Test 2: Predefined Scenarios")
    
    scenarios = [
        ScenarioBuilder.create_recession_scenario(),
        ScenarioBuilder.create_inflation_shock_scenario(),
        ScenarioBuilder.create_liquidity_crisis_scenario(),
        ScenarioBuilder.create_geopolitical_crisis_scenario()
    ]
    
    for scenario in scenarios:
        print(f"\n" + "="*50)
        print(scenario.summary())
    
    # Test 3: Builder chaining
    print("\n📊 Test 3: Builder Pattern")
    
    scenario2 = (ScenarioBuilder()
                 .add_broad_market_shock(-0.10)
                 .add_volatility_spike(1.5)
                 .build("Market Correction"))
    
    print(f"\n{scenario2.summary()}")
    
    # Test 4: Summary table
    print("\n📊 Test 4: Scenario Comparison")
    print(f"{'Scenario':<25} {'Equity Shock':<15} {'Vol Mult':<12} {'Corr Adj':<12}")
    print("-" * 64)
    
    all_scenarios = [scenario1] + scenarios + [scenario2]
    
    for scenario in all_scenarios:
        equity_shock = scenario.market_shocks.get('SPY', 0)
        vol_mult = scenario.volatility_multiplier
        corr_adj = scenario.correlation_adjustment
        
        print(f"{scenario.name:<25} {equity_shock*100:<15.1f}% {vol_mult:<12.1f}x {corr_adj*100:<12.1f}%")
    
    print("\n" + "=" * 70)
    print("✅ Scenario builder test complete!")
    print("=" * 70)
