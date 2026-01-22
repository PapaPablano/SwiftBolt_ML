"""Multi-leg options strategy builder with predefined strategies.

Easily construct complex options strategies with risk/reward analysis.

Usage:
    from src.strategies.strategy_builder import StrategyBuilder
    
    # Build iron condor
    builder = StrategyBuilder()
    strategy = builder.iron_condor(
        underlying_price=100,
        wing_width=5,
        distance_from_atm=10
    )
    
    # Analyze
    print(strategy.summary())
    
    # Visualize
    fig = strategy.plot()
    fig.show()

References:
    - McMillan, L. G. (2012). "Options as a Strategic Investment"
    - Cohen, G. (2005). "The Bible of Options Strategies"
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..visualization.payoff_diagrams import PayoffDiagram, OptionLeg

logger = logging.getLogger(__name__)


@dataclass
class Strategy:
    """Represents a complete options strategy.
    
    Attributes:
        name: Strategy name
        legs: List of option legs
        underlying_price: Current underlying price
        description: Strategy description
        margin_requirement: Estimated margin requirement
    """
    name: str
    legs: List[OptionLeg] = field(default_factory=list)
    underlying_price: float = 0.0
    description: str = ""
    margin_requirement: float = 0.0
    
    def add_leg(self, leg: OptionLeg):
        """Add an option leg to the strategy."""
        self.legs.append(leg)
    
    def summary(self) -> Dict:
        """Get strategy summary with metrics."""
        diagram = PayoffDiagram(self.name)
        for leg in self.legs:
            diagram.legs.append(leg)
        
        summary = diagram.get_summary()
        summary['margin_requirement'] = self.margin_requirement
        summary['description'] = self.description
        summary['num_legs'] = len(self.legs)
        
        return summary
    
    def plot(self, **kwargs):
        """Generate payoff diagram."""
        diagram = PayoffDiagram(self.name)
        for leg in self.legs:
            diagram.legs.append(leg)
        
        return diagram.plot(
            current_price=self.underlying_price if self.underlying_price > 0 else None,
            **kwargs
        )
    
    def print_summary(self):
        """Print strategy summary."""
        summary = self.summary()
        
        print("=" * 70)
        print(f"Strategy: {self.name}")
        print("=" * 70)
        if self.description:
            print(f"Description: {self.description}")
        print(f"Number of Legs: {summary['num_legs']}")
        print(f"Initial {summary['cost_type']}: ${abs(summary['initial_cost']):.2f}")
        print(f"Margin Requirement: ${self.margin_requirement:.2f}")
        print(f"\nMax Profit: ${summary['max_profit']:.2f}")
        print(f"Max Loss: ${summary['max_loss']:.2f}")
        print(f"Risk/Reward Ratio: {summary['risk_reward_ratio']:.2f}")
        print(f"\nBreak-even Points: {[f'${be:.2f}' for be in summary['break_even_points']]}")
        print("=" * 70)


class StrategyBuilder:
    """Builder for common options strategies."""
    
    @staticmethod
    def long_call(
        underlying_price: float,
        strike: float,
        premium: float,
        quantity: int = 1
    ) -> Strategy:
        """Build long call strategy.
        
        Args:
            underlying_price: Current underlying price
            strike: Call strike
            premium: Call premium
            quantity: Number of contracts
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name="Long Call",
            underlying_price=underlying_price,
            description="Bullish strategy with unlimited upside, limited downside"
        )
        
        leg = OptionLeg('call', strike, premium, quantity)
        strategy.add_leg(leg)
        
        # Margin: Premium paid
        strategy.margin_requirement = premium * quantity * 100
        
        return strategy
    
    @staticmethod
    def bull_call_spread(
        underlying_price: float,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        quantity: int = 1
    ) -> Strategy:
        """Build bull call spread.
        
        Args:
            underlying_price: Current price
            long_strike: Lower strike (buy)
            short_strike: Higher strike (sell)
            long_premium: Premium for long call
            short_premium: Premium for short call
            quantity: Number of spreads
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name="Bull Call Spread",
            underlying_price=underlying_price,
            description="Bullish spread with limited profit and loss"
        )
        
        strategy.add_leg(OptionLeg('call', long_strike, long_premium, quantity))
        strategy.add_leg(OptionLeg('call', short_strike, short_premium, -quantity))
        
        # Margin: Net debit
        net_debit = (long_premium - short_premium) * quantity * 100
        strategy.margin_requirement = max(net_debit, 0)
        
        return strategy
    
    @staticmethod
    def iron_condor(
        underlying_price: float,
        call_sell_strike: float,
        call_buy_strike: float,
        put_sell_strike: float,
        put_buy_strike: float,
        call_sell_premium: float,
        call_buy_premium: float,
        put_sell_premium: float,
        put_buy_premium: float,
        quantity: int = 1
    ) -> Strategy:
        """Build iron condor strategy.
        
        Args:
            underlying_price: Current price
            call_sell_strike: Short call strike
            call_buy_strike: Long call strike (higher)
            put_sell_strike: Short put strike
            put_buy_strike: Long put strike (lower)
            *_premium: Premiums for each leg
            quantity: Number of condors
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name="Iron Condor",
            underlying_price=underlying_price,
            description="Neutral strategy selling OTM put and call spreads"
        )
        
        # Call spread
        strategy.add_leg(OptionLeg('call', call_sell_strike, call_sell_premium, -quantity))
        strategy.add_leg(OptionLeg('call', call_buy_strike, call_buy_premium, quantity))
        
        # Put spread
        strategy.add_leg(OptionLeg('put', put_sell_strike, put_sell_premium, -quantity))
        strategy.add_leg(OptionLeg('put', put_buy_strike, put_buy_premium, quantity))
        
        # Margin: Width of widest spread
        call_width = (call_buy_strike - call_sell_strike) * 100 * quantity
        put_width = (put_sell_strike - put_buy_strike) * 100 * quantity
        strategy.margin_requirement = max(call_width, put_width)
        
        return strategy
    
    @staticmethod
    def straddle(
        underlying_price: float,
        strike: float,
        call_premium: float,
        put_premium: float,
        quantity: int = 1,
        long: bool = True
    ) -> Strategy:
        """Build straddle (long or short).
        
        Args:
            underlying_price: Current price
            strike: Strike (typically ATM)
            call_premium: Call premium
            put_premium: Put premium
            quantity: Number of straddles
            long: True for long straddle, False for short
        
        Returns:
            Strategy object
        """
        direction = "Long" if long else "Short"
        qty_multiplier = 1 if long else -1
        
        strategy = Strategy(
            name=f"{direction} Straddle",
            underlying_price=underlying_price,
            description=f"{'High volatility' if long else 'Low volatility'} strategy"
        )
        
        strategy.add_leg(OptionLeg('call', strike, call_premium, quantity * qty_multiplier))
        strategy.add_leg(OptionLeg('put', strike, put_premium, quantity * qty_multiplier))
        
        # Margin
        if long:
            strategy.margin_requirement = (call_premium + put_premium) * quantity * 100
        else:
            # Short straddle: higher margin
            strategy.margin_requirement = strike * 100 * quantity * 0.20  # Simplified
        
        return strategy
    
    @staticmethod
    def butterfly_spread(
        underlying_price: float,
        lower_strike: float,
        middle_strike: float,
        upper_strike: float,
        lower_premium: float,
        middle_premium: float,
        upper_premium: float,
        option_type: str = 'call',
        quantity: int = 1
    ) -> Strategy:
        """Build butterfly spread.
        
        Args:
            underlying_price: Current price
            lower_strike: Lowest strike
            middle_strike: Middle strike (ATM)
            upper_strike: Highest strike
            *_premium: Premiums for each strike
            option_type: 'call' or 'put'
            quantity: Number of butterflies
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name=f"{option_type.capitalize()} Butterfly Spread",
            underlying_price=underlying_price,
            description="Low-risk strategy for neutral market expectations"
        )
        
        # Long 1 lower, short 2 middle, long 1 upper
        strategy.add_leg(OptionLeg(option_type, lower_strike, lower_premium, quantity))
        strategy.add_leg(OptionLeg(option_type, middle_strike, middle_premium, -2 * quantity))
        strategy.add_leg(OptionLeg(option_type, upper_strike, upper_premium, quantity))
        
        # Margin: Net debit
        net_debit = (lower_premium - 2 * middle_premium + upper_premium) * quantity * 100
        strategy.margin_requirement = max(net_debit, 0)
        
        return strategy
    
    @staticmethod
    def covered_call(
        underlying_price: float,
        shares: int,
        call_strike: float,
        call_premium: float,
        quantity: int = 1
    ) -> Strategy:
        """Build covered call strategy.
        
        Note: Simplified - doesn't fully model stock position
        
        Args:
            underlying_price: Current price
            shares: Number of shares owned
            call_strike: Short call strike
            call_premium: Call premium received
            quantity: Number of calls
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name="Covered Call",
            underlying_price=underlying_price,
            description="Generate income on stock holdings"
        )
        
        # Short call
        strategy.add_leg(OptionLeg('call', call_strike, call_premium, -quantity))
        
        # Stock (simplified - would need special handling)
        # For margin, assume stock is fully paid
        strategy.margin_requirement = 0  # Stock acts as collateral
        
        return strategy
    
    @staticmethod
    def custom_strategy(
        name: str,
        legs: List[Dict],
        underlying_price: float,
        description: str = ""
    ) -> Strategy:
        """Build custom strategy from leg definitions.
        
        Args:
            name: Strategy name
            legs: List of leg dicts with keys: option_type, strike, premium, quantity
            underlying_price: Current price
            description: Strategy description
        
        Returns:
            Strategy object
        """
        strategy = Strategy(
            name=name,
            underlying_price=underlying_price,
            description=description
        )
        
        for leg_def in legs:
            leg = OptionLeg(
                option_type=leg_def['option_type'],
                strike=leg_def['strike'],
                premium=leg_def['premium'],
                quantity=leg_def.get('quantity', 1)
            )
            strategy.add_leg(leg)
        
        # Estimate margin (simplified)
        total_cost = sum(
            leg.premium * abs(leg.quantity) * 100 
            for leg in strategy.legs if leg.quantity > 0
        )
        strategy.margin_requirement = total_cost
        
        return strategy


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Strategy Builder - Self Test")
    print("=" * 70)
    
    builder = StrategyBuilder()
    underlying = 100
    
    # Test 1: Bull Call Spread
    print("\n📊 Test 1: Bull Call Spread")
    strategy1 = builder.bull_call_spread(
        underlying_price=underlying,
        long_strike=100,
        short_strike=110,
        long_premium=5.0,
        short_premium=2.0
    )
    strategy1.print_summary()
    
    # Test 2: Iron Condor
    print("\n📊 Test 2: Iron Condor")
    strategy2 = builder.iron_condor(
        underlying_price=underlying,
        call_sell_strike=110,
        call_buy_strike=115,
        put_sell_strike=90,
        put_buy_strike=85,
        call_sell_premium=3.0,
        call_buy_premium=1.5,
        put_sell_premium=3.0,
        put_buy_premium=1.5
    )
    strategy2.print_summary()
    
    # Test 3: Long Straddle
    print("\n📊 Test 3: Long Straddle")
    strategy3 = builder.straddle(
        underlying_price=underlying,
        strike=100,
        call_premium=5.0,
        put_premium=5.0,
        long=True
    )
    strategy3.print_summary()
    
    # Test 4: Butterfly
    print("\n📊 Test 4: Butterfly Spread")
    strategy4 = builder.butterfly_spread(
        underlying_price=underlying,
        lower_strike=95,
        middle_strike=100,
        upper_strike=105,
        lower_premium=7.0,
        middle_premium=5.0,
        upper_premium=3.0,
        option_type='call'
    )
    strategy4.print_summary()
    
    print("\n" + "=" * 70)
    print("✅ All strategies built successfully!")
    print("=" * 70)
