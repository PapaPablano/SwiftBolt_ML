"""
Options Strategies Skill Package

Expert-level options trading framework for multi-leg strategy design,
quantitative modeling, and programmatic execution using Alpaca Markets APIs.

Author: Ordinis-1 Project
License: Educational Use
"""

__version__ = "1.0.0"
__author__ = "Ordinis-1 Project"

from .option_pricing import (
    BlackScholesCalculator,
    OptionParameters,
    calculate_expected_move,
    calculate_implied_volatility,
)
from .strategy_builder import MultiLegStrategy, OptionLeg, OptionType, PositionSide, StrategyBuilder

__all__ = [
    # Pricing
    "BlackScholesCalculator",
    "OptionParameters",
    "calculate_implied_volatility",
    "calculate_expected_move",
    # Strategy Building
    "StrategyBuilder",
    "MultiLegStrategy",
    "OptionLeg",
    "OptionType",
    "PositionSide",
]
