#!/usr/bin/env python3
"""
CLI script to run stress tests on a portfolio.
Returns JSON output for use by Edge Functions.

Usage:
    python run_stress_test.py --positions '{"AAPL": 100, "MSFT": 50}' --prices '{"AAPL": 150, "MSFT": 300}' --scenario 2008_financial_crisis
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.stress_testing import StressTester, HISTORICAL_SCENARIOS

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs
logger = logging.getLogger(__name__)


def run_stress_test(
    positions: Dict[str, float],
    current_prices: Dict[str, float],
    scenario_name: Optional[str] = None,
    custom_shocks: Optional[Dict[str, float]] = None,
    var_level: float = 0.05
) -> dict:
    """
    Run stress test on portfolio.
    
    Args:
        positions: Dictionary of {symbol: quantity}
        current_prices: Dictionary of {symbol: current_price}
        scenario_name: Name of historical scenario (optional)
        custom_shocks: Custom shocks dictionary {symbol: price_change_pct} (optional)
        var_level: VaR confidence level (e.g., 0.05 for 95% VaR)
        
    Returns:
        Dictionary with stress test results
    """
    try:
        # Initialize stress tester
        tester = StressTester(positions, current_prices, var_level=var_level)
        
        # Run stress test
        if scenario_name:
            if scenario_name not in HISTORICAL_SCENARIOS:
                available = list(HISTORICAL_SCENARIOS.keys())
                return {
                    "error": f"Unknown scenario: {scenario_name}. Available: {', '.join(available)}",
                    "scenario": scenario_name
                }
            result = tester.historical_stress_test(scenario_name)
        elif custom_shocks:
            result = tester.custom_scenario(custom_shocks, scenario_name="Custom Scenario")
        else:
            return {
                "error": "Either scenario_name or custom_shocks must be provided",
                "positions": positions
            }
        
        # Convert to JSON-serializable format
        position_changes = {k: float(v) for k, v in result.position_changes.items()}
        
        return {
            "scenario": result.scenario_name,
            "portfolio": {
                "currentValue": float(tester.portfolio_value),
                "change": float(result.portfolio_change),
                "changePercent": float(result.portfolio_change_pct)
            },
            "risk": {
                "varLevel": float(var_level),
                "varBreached": bool(result.var_breached),
                "severity": result.severity
            },
            "positionChanges": position_changes,
            "positions": {k: float(v) for k, v in positions.items()},
            "prices": {k: float(v) for k, v in current_prices.items()}
        }
        
    except Exception as e:
        logger.error(f"Error running stress test: {e}", exc_info=True)
        return {
            "error": str(e),
            "scenario": scenario_name or "custom"
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run stress test on portfolio")
    parser.add_argument("--positions", required=True, help="JSON dict of {symbol: quantity}")
    parser.add_argument("--prices", required=True, help="JSON dict of {symbol: current_price}")
    parser.add_argument("--scenario", help="Historical scenario name (optional)")
    parser.add_argument("--custom-shocks", help="JSON dict of {symbol: price_change_pct} (optional)")
    parser.add_argument("--var-level", type=float, default=0.05, help="VaR confidence level")
    
    args = parser.parse_args()
    
    # Parse JSON arguments
    try:
        positions = json.loads(args.positions)
        prices = json.loads(args.prices)
        custom_shocks = json.loads(args.custom_shocks) if args.custom_shocks else None
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}, indent=2))
        sys.exit(1)
    
    result = run_stress_test(
        positions=positions,
        current_prices=prices,
        scenario_name=args.scenario,
        custom_shocks=custom_shocks,
        var_level=args.var_level
    )
    
    # Output JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
