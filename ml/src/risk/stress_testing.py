"""Stress testing and scenario analysis for portfolio risk management.

Implements historical and hypothetical stress tests to assess
portfolio behavior under extreme market conditions.

Usage:
    from src.risk.stress_testing import StressTester
    
    # Initialize
    tester = StressTester(portfolio_positions, current_prices)
    
    # Run historical stress test
    results = tester.historical_stress_test('2008_financial_crisis')
    
    # Run custom scenario
    results = tester.custom_scenario({'SPY': -0.20, 'TLT': 0.10})

References:
    - Basel Committee on Banking Supervision (2009). "Principles for 
      sound stress testing practices and supervision"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StressTestResult:
    """Results from a stress test.
    
    Attributes:
        scenario_name: Name of scenario
        portfolio_change: Total portfolio change ($)
        portfolio_change_pct: Portfolio change (%)
        position_changes: Changes by position
        var_breached: Whether VaR was breached
        severity: Severity level (Low, Medium, High, Extreme)
    """
    scenario_name: str
    portfolio_change: float
    portfolio_change_pct: float
    position_changes: Dict[str, float]
    var_breached: bool
    severity: str
    
    def summary(self) -> str:
        """Get formatted summary."""
        return (
            f"Scenario: {self.scenario_name}\n"
            f"Portfolio Impact: ${self.portfolio_change:,.2f} ({self.portfolio_change_pct:.2%})\n"
            f"Severity: {self.severity}\n"
            f"VaR Breached: {'Yes' if self.var_breached else 'No'}"
        )


# Historical stress scenarios (approximate market moves)
HISTORICAL_SCENARIOS = {
    '2008_financial_crisis': {
        'description': '2008 Financial Crisis (Sep-Oct 2008)',
        'shocks': {
            'SPY': -0.35,  # S&P 500
            'QQQ': -0.40,  # NASDAQ
            'IWM': -0.38,  # Small caps
            'TLT': 0.15,   # Long-term treasuries
            'GLD': -0.05,  # Gold
            'USD': 0.10    # Dollar
        }
    },
    '2020_covid_crash': {
        'description': 'COVID-19 Crash (Feb-Mar 2020)',
        'shocks': {
            'SPY': -0.34,
            'QQQ': -0.30,
            'IWM': -0.42,
            'TLT': 0.20,
            'GLD': 0.05,
            'VIX': 3.50  # 350% increase
        }
    },
    '2011_eu_debt_crisis': {
        'description': 'European Debt Crisis (2011)',
        'shocks': {
            'SPY': -0.19,
            'QQQ': -0.18,
            'EWG': -0.30,  # Germany
            'EWI': -0.35,  # Italy
            'TLT': 0.25,
            'EUR': -0.15
        }
    },
    '1987_black_monday': {
        'description': 'Black Monday (Oct 19, 1987)',
        'shocks': {
            'SPY': -0.22,  # Single day
            'QQQ': -0.25,
            'TLT': 0.10,
            'VIX': 2.0
        }
    },
    '2015_china_devaluation': {
        'description': 'China Devaluation (Aug 2015)',
        'shocks': {
            'SPY': -0.11,
            'QQQ': -0.13,
            'EEM': -0.18,  # Emerging markets
            'FXI': -0.25,  # China
            'USD': 0.05
        }
    }
}


class StressTester:
    """Portfolio stress testing framework."""
    
    def __init__(
        self,
        positions: Dict[str, float],
        current_prices: Dict[str, float],
        var_level: float = 0.05
    ):
        """Initialize stress tester.
        
        Args:
            positions: Dictionary of {symbol: quantity}
            current_prices: Dictionary of {symbol: current_price}
            var_level: VaR confidence level (e.g., 0.05 for 95% VaR)
        """
        self.positions = positions
        self.current_prices = current_prices
        self.var_level = var_level
        
        # Calculate current portfolio value
        self.portfolio_value = sum(
            positions.get(symbol, 0) * current_prices.get(symbol, 0)
            for symbol in positions.keys()
        )
        
        logger.info(
            f"StressTester initialized: ${self.portfolio_value:,.2f} portfolio value, "
            f"{len(positions)} positions"
        )
    
    def _apply_shocks(
        self,
        shocks: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply price shocks to portfolio.
        
        Args:
            shocks: Dictionary of {symbol: price_change_pct}
        
        Returns:
            Dictionary of position-level P&L changes
        """
        position_changes = {}
        
        for symbol, quantity in self.positions.items():
            current_price = self.current_prices.get(symbol, 0)
            
            if current_price == 0:
                position_changes[symbol] = 0
                continue
            
            # Find applicable shock
            shock_pct = 0
            
            # Direct match
            if symbol in shocks:
                shock_pct = shocks[symbol]
            # Try to match against broad indices/categories
            else:
                # Apply a default equity shock if symbol not found
                if 'SPY' in shocks:
                    shock_pct = shocks['SPY'] * 0.8  # Assume 80% correlation
                    logger.debug(f"Using SPY shock for {symbol}: {shock_pct:.2%}")
            
            # Calculate price change
            new_price = current_price * (1 + shock_pct)
            pnl_change = quantity * (new_price - current_price)
            
            position_changes[symbol] = pnl_change
        
        return position_changes
    
    def _classify_severity(self, portfolio_change_pct: float) -> str:
        """Classify stress test severity.
        
        Args:
            portfolio_change_pct: Portfolio change percentage
        
        Returns:
            Severity level
        """
        abs_change = abs(portfolio_change_pct)
        
        if abs_change < 0.05:
            return "Low"
        elif abs_change < 0.10:
            return "Medium"
        elif abs_change < 0.20:
            return "High"
        else:
            return "Extreme"
    
    def historical_stress_test(
        self,
        scenario_name: str
    ) -> StressTestResult:
        """Run historical stress test.
        
        Args:
            scenario_name: Name of historical scenario
        
        Returns:
            StressTestResult
        """
        if scenario_name not in HISTORICAL_SCENARIOS:
            available = ', '.join(HISTORICAL_SCENARIOS.keys())
            raise ValueError(
                f"Unknown scenario: {scenario_name}. "
                f"Available: {available}"
            )
        
        scenario = HISTORICAL_SCENARIOS[scenario_name]
        shocks = scenario['shocks']
        
        logger.info(f"Running historical stress test: {scenario['description']}")
        
        # Apply shocks
        position_changes = self._apply_shocks(shocks)
        
        # Calculate total impact
        portfolio_change = sum(position_changes.values())
        portfolio_change_pct = portfolio_change / self.portfolio_value if self.portfolio_value > 0 else 0
        
        # Determine if VaR was breached (simplified)
        var_threshold = -self.portfolio_value * self.var_level
        var_breached = portfolio_change < var_threshold
        
        # Classify severity
        severity = self._classify_severity(portfolio_change_pct)
        
        return StressTestResult(
            scenario_name=scenario['description'],
            portfolio_change=portfolio_change,
            portfolio_change_pct=portfolio_change_pct,
            position_changes=position_changes,
            var_breached=var_breached,
            severity=severity
        )
    
    def custom_scenario(
        self,
        shocks: Dict[str, float],
        scenario_name: str = "Custom Scenario"
    ) -> StressTestResult:
        """Run custom stress test scenario.
        
        Args:
            shocks: Dictionary of {symbol: price_change_pct}
            scenario_name: Name for this scenario
        
        Returns:
            StressTestResult
        """
        logger.info(f"Running custom stress test: {scenario_name}")
        
        # Apply shocks
        position_changes = self._apply_shocks(shocks)
        
        # Calculate total impact
        portfolio_change = sum(position_changes.values())
        portfolio_change_pct = portfolio_change / self.portfolio_value if self.portfolio_value > 0 else 0
        
        # Determine if VaR was breached
        var_threshold = -self.portfolio_value * self.var_level
        var_breached = portfolio_change < var_threshold
        
        # Classify severity
        severity = self._classify_severity(portfolio_change_pct)
        
        return StressTestResult(
            scenario_name=scenario_name,
            portfolio_change=portfolio_change,
            portfolio_change_pct=portfolio_change_pct,
            position_changes=position_changes,
            var_breached=var_breached,
            severity=severity
        )
    
    def correlation_breakdown(
        self,
        correlation_increase: float = 0.50
    ) -> StressTestResult:
        """Simulate correlation breakdown scenario.
        
        In crisis periods, correlations tend to increase (diversification fails).
        
        Args:
            correlation_increase: How much correlations increase (e.g., 0.5 for 50% increase)
        
        Returns:
            StressTestResult
        """
        # Simulate a scenario where all assets move down together
        # with increased correlation
        
        shocks = {}
        for symbol in self.positions.keys():
            # Base shock (negative)
            base_shock = -0.15
            
            # Add correlation effect (makes it worse)
            correlation_effect = base_shock * correlation_increase
            
            shocks[symbol] = base_shock + correlation_effect
        
        return self.custom_scenario(shocks, "Correlation Breakdown")
    
    def run_all_historical_tests(self) -> List[StressTestResult]:
        """Run all historical stress tests.
        
        Returns:
            List of StressTestResult
        """
        results = []
        
        for scenario_name in HISTORICAL_SCENARIOS.keys():
            try:
                result = self.historical_stress_test(scenario_name)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in scenario {scenario_name}: {e}")
        
        return results


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Stress Tester - Self Test")
    print("=" * 70)
    
    # Create sample portfolio
    positions = {
        'SPY': 100,   # S&P 500 ETF
        'QQQ': 50,    # NASDAQ ETF
        'TLT': 30,    # Treasury bonds
        'GLD': 20     # Gold
    }
    
    current_prices = {
        'SPY': 450,
        'QQQ': 380,
        'TLT': 95,
        'GLD': 180
    }
    
    # Calculate portfolio value
    portfolio_value = sum(
        positions[s] * current_prices[s]
        for s in positions.keys()
    )
    
    print(f"\nPortfolio Composition:")
    print(f"Total Value: ${portfolio_value:,.0f}")
    for symbol, qty in positions.items():
        value = qty * current_prices[symbol]
        pct = (value / portfolio_value) * 100
        print(f"  {symbol}: {qty} units @ ${current_prices[symbol]} = ${value:,.0f} ({pct:.1f}%)")
    
    # Initialize tester
    tester = StressTester(positions, current_prices, var_level=0.05)
    
    # Test 1: Single historical scenario
    print("\n📊 Test 1: 2008 Financial Crisis Scenario")
    result1 = tester.historical_stress_test('2008_financial_crisis')
    print(f"\n{result1.summary()}")
    
    print(f"\nPosition-Level Impacts:")
    for symbol, change in result1.position_changes.items():
        print(f"  {symbol}: ${change:,.2f}")
    
    # Test 2: COVID crash
    print("\n📊 Test 2: COVID-19 Crash Scenario")
    result2 = tester.historical_stress_test('2020_covid_crash')
    print(f"\n{result2.summary()}")
    
    # Test 3: Custom scenario
    print("\n📊 Test 3: Custom Scenario (Market Correction)")
    custom_shocks = {
        'SPY': -0.10,
        'QQQ': -0.15,
        'TLT': 0.05,
        'GLD': 0.02
    }
    result3 = tester.custom_scenario(custom_shocks, "Market Correction -10%")
    print(f"\n{result3.summary()}")
    
    # Test 4: Correlation breakdown
    print("\n📊 Test 4: Correlation Breakdown")
    result4 = tester.correlation_breakdown(correlation_increase=0.50)
    print(f"\n{result4.summary()}")
    
    # Test 5: Run all historical tests
    print("\n📊 Test 5: All Historical Scenarios")
    all_results = tester.run_all_historical_tests()
    
    print(f"\n{'Scenario':<40} {'Impact':<15} {'Severity':<10}")
    print("-" * 65)
    
    for result in all_results:
        print(f"{result.scenario_name:<40} {result.portfolio_change_pct*100:<15.2f}% {result.severity:<10}")
    
    # Summary
    print("\n📊 Worst Case Scenario:")
    worst = min(all_results, key=lambda r: r.portfolio_change_pct)
    print(f"  Scenario: {worst.scenario_name}")
    print(f"  Impact: {worst.portfolio_change_pct:.2%}")
    print(f"  Dollar Loss: ${worst.portfolio_change:,.2f}")
    
    print("\n" + "=" * 70)
    print("✅ Stress testing complete!")
    print("=" * 70)
