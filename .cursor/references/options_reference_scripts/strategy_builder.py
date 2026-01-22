"""
Multi-Leg Options Strategy Builder

Utility for constructing and analyzing multi-leg options strategies including
straddles, strangles, butterflies, condors, and spreads.

Author: Ordinis-1 Project
License: Educational Use
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class OptionType(Enum):
    """Option type enumeration."""

    CALL = "call"
    PUT = "put"


class PositionSide(Enum):
    """Position side enumeration."""

    LONG = "long"  # Buy
    SHORT = "short"  # Sell


@dataclass
class OptionLeg:
    """Represents a single option leg in a strategy."""

    option_type: OptionType
    strike: float
    expiration: str  # Date or days to expiration
    position_side: PositionSide
    quantity: int = 1
    premium: float = 0.0  # Premium per contract

    def __post_init__(self):
        """Validate leg parameters."""
        if self.strike <= 0:
            raise ValueError("Strike must be positive")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")


@dataclass
class MultiLegStrategy:
    """Represents a complete multi-leg options strategy."""

    name: str
    legs: list[OptionLeg] = field(default_factory=list)
    underlying_symbol: str = ""
    underlying_price: float = 0.0

    def add_leg(self, leg: OptionLeg) -> None:
        """Add a leg to the strategy."""
        self.legs.append(leg)

    def net_premium(self) -> float:
        """
        Calculate net premium paid/received.

        Returns:
            Positive value = net credit (received premium)
            Negative value = net debit (paid premium)
        """
        total = 0.0
        for leg in self.legs:
            multiplier = 100 * leg.quantity  # Options are per 100 shares

            if leg.position_side == PositionSide.LONG:
                total -= leg.premium * multiplier  # Paid premium (debit)
            else:
                total += leg.premium * multiplier  # Received premium (credit)

        return total

    def max_profit(self, price_range: np.ndarray | None = None) -> tuple[float, float]:
        """
        Calculate maximum profit and price at which it occurs.

        Args:
            price_range: Array of prices to evaluate. If None, uses reasonable range.

        Returns:
            Tuple of (max_profit, price_at_max_profit)
        """
        if price_range is None:
            # Create price range around strikes
            strikes = [leg.strike for leg in self.legs]
            min_strike = min(strikes)
            max_strike = max(strikes)
            price_range = np.linspace(min_strike * 0.8, max_strike * 1.2, 1000)

        profits = self.calculate_payoff(price_range)
        max_idx = np.argmax(profits)

        return profits[max_idx], price_range[max_idx]

    def max_loss(self, price_range: np.ndarray | None = None) -> tuple[float, float]:
        """
        Calculate maximum loss and price at which it occurs.

        Returns:
            Tuple of (max_loss, price_at_max_loss)
        """
        if price_range is None:
            strikes = [leg.strike for leg in self.legs]
            min_strike = min(strikes)
            max_strike = max(strikes)
            price_range = np.linspace(min_strike * 0.8, max_strike * 1.2, 1000)

        profits = self.calculate_payoff(price_range)
        min_idx = np.argmin(profits)

        return profits[min_idx], price_range[min_idx]

    def breakeven_points(self, price_range: np.ndarray | None = None) -> list[float]:
        """
        Calculate breakeven points where P/L = 0.

        Returns:
            List of breakeven prices
        """
        if price_range is None:
            strikes = [leg.strike for leg in self.legs]
            min_strike = min(strikes)
            max_strike = max(strikes)
            price_range = np.linspace(min_strike * 0.7, max_strike * 1.3, 10000)

        profits = self.calculate_payoff(price_range)

        # Find zero crossings
        breakevens = []
        for i in range(len(profits) - 1):
            if profits[i] * profits[i + 1] < 0:  # Sign change
                # Linear interpolation for more precise breakeven
                x1, x2 = price_range[i], price_range[i + 1]
                y1, y2 = profits[i], profits[i + 1]
                breakeven = x1 - y1 * (x2 - x1) / (y2 - y1)
                breakevens.append(breakeven)

        return breakevens

    def calculate_payoff(self, prices: np.ndarray) -> np.ndarray:
        """
        Calculate total P/L at expiration for given prices.

        Args:
            prices: Array of underlying prices to evaluate

        Returns:
            Array of P/L values
        """
        total_payoff = np.zeros_like(prices, dtype=float)

        for leg in self.legs:
            multiplier = 100 * leg.quantity

            # Calculate intrinsic value at expiration
            if leg.option_type == OptionType.CALL:
                intrinsic = np.maximum(prices - leg.strike, 0)
            else:  # PUT
                intrinsic = np.maximum(leg.strike - prices, 0)

            # Apply position side
            if leg.position_side == PositionSide.LONG:
                leg_payoff = (intrinsic - leg.premium) * multiplier
            else:  # SHORT
                leg_payoff = (leg.premium - intrinsic) * multiplier

            total_payoff += leg_payoff

        return total_payoff

    def summary(self) -> dict:
        """
        Generate strategy summary with key metrics.

        Returns:
            Dictionary with strategy metrics
        """
        max_prof, price_max_prof = self.max_profit()
        max_ls, price_max_ls = self.max_loss()
        breakevens = self.breakeven_points()

        return {
            "name": self.name,
            "num_legs": len(self.legs),
            "net_premium": self.net_premium(),
            "strategy_type": "CREDIT" if self.net_premium() > 0 else "DEBIT",
            "max_profit": max_prof,
            "max_loss": max_ls,
            "breakeven_points": breakevens,
            "risk_reward_ratio": abs(max_prof / max_ls) if max_ls != 0 else float("inf"),
        }


class StrategyBuilder:
    """Builder for common multi-leg options strategies."""

    @staticmethod
    def long_straddle(
        underlying_price: float,
        strike: float | None = None,
        expiration: str = "30D",
        call_premium: float = 5.0,
        put_premium: float = 4.5,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build a long straddle strategy.

        Structure: Buy ATM call + Buy ATM put

        Args:
            underlying_price: Current stock price
            strike: Strike price (defaults to ATM)
            expiration: Expiration date or days
            call_premium: Call premium per contract
            put_premium: Put premium per contract
            symbol: Underlying symbol

        Returns:
            MultiLegStrategy object

        Example:
            >>> strategy = StrategyBuilder.long_straddle(
            ...     underlying_price=100, strike=100,
            ...     call_premium=5.0, put_premium=4.5
            ... )
            >>> summary = strategy.summary()
        """
        if strike is None:
            strike = underlying_price

        strategy = MultiLegStrategy(
            name="Long Straddle", underlying_symbol=symbol, underlying_price=underlying_price
        )

        # Buy ATM call
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=call_premium,
            )
        )

        # Buy ATM put
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=put_premium,
            )
        )

        return strategy

    @staticmethod
    def long_strangle(
        underlying_price: float,
        put_strike: float,
        call_strike: float,
        expiration: str = "30D",
        call_premium: float = 3.0,
        put_premium: float = 2.5,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build a long strangle strategy.

        Structure: Buy OTM call + Buy OTM put

        Args:
            underlying_price: Current stock price
            put_strike: Put strike (below current price)
            call_strike: Call strike (above current price)
            expiration: Expiration date or days
            call_premium: Call premium per contract
            put_premium: Put premium per contract
            symbol: Underlying symbol

        Returns:
            MultiLegStrategy object
        """
        strategy = MultiLegStrategy(
            name="Long Strangle", underlying_symbol=symbol, underlying_price=underlying_price
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=call_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=call_premium,
            )
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=put_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=put_premium,
            )
        )

        return strategy

    @staticmethod
    def iron_butterfly(
        underlying_price: float,
        atm_strike: float | None = None,
        wing_width: float = 10.0,
        expiration: str = "30D",
        short_call_premium: float = 5.0,
        short_put_premium: float = 4.5,
        long_call_premium: float = 1.0,
        long_put_premium: float = 0.8,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build an iron butterfly strategy.

        Structure:
        - Sell ATM call
        - Sell ATM put
        - Buy OTM call (wing)
        - Buy OTM put (wing)

        Args:
            underlying_price: Current stock price
            atm_strike: ATM strike (defaults to current price)
            wing_width: Distance to wings from ATM
            expiration: Expiration date or days
            short_call_premium: Short call premium
            short_put_premium: Short put premium
            long_call_premium: Long call premium
            long_put_premium: Long put premium
            symbol: Underlying symbol

        Returns:
            MultiLegStrategy object
        """
        if atm_strike is None:
            atm_strike = underlying_price

        strategy = MultiLegStrategy(
            name="Iron Butterfly", underlying_symbol=symbol, underlying_price=underlying_price
        )

        # Sell ATM call
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=atm_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=short_call_premium,
            )
        )

        # Sell ATM put
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=atm_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=short_put_premium,
            )
        )

        # Buy OTM call (upper wing)
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=atm_strike + wing_width,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=long_call_premium,
            )
        )

        # Buy OTM put (lower wing)
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=atm_strike - wing_width,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=long_put_premium,
            )
        )

        return strategy

    @staticmethod
    def iron_condor(
        underlying_price: float,
        put_short_strike: float,
        put_long_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        expiration: str = "30D",
        put_short_premium: float = 2.0,
        put_long_premium: float = 0.8,
        call_short_premium: float = 2.2,
        call_long_premium: float = 0.9,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build an iron condor strategy.

        Structure:
        - Sell OTM put
        - Buy further OTM put
        - Sell OTM call
        - Buy further OTM call

        Returns:
            MultiLegStrategy object
        """
        strategy = MultiLegStrategy(
            name="Iron Condor", underlying_symbol=symbol, underlying_price=underlying_price
        )

        # Put spread (bull put spread)
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=put_short_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=put_short_premium,
            )
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=put_long_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=put_long_premium,
            )
        )

        # Call spread (bear call spread)
        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=call_short_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=call_short_premium,
            )
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=call_long_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=call_long_premium,
            )
        )

        return strategy

    @staticmethod
    def bull_call_spread(
        underlying_price: float,
        long_strike: float,
        short_strike: float,
        expiration: str = "30D",
        long_premium: float = 6.0,
        short_premium: float = 2.5,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build a bull call spread strategy.

        Structure: Buy lower strike call + Sell higher strike call

        Returns:
            MultiLegStrategy object
        """
        strategy = MultiLegStrategy(
            name="Bull Call Spread", underlying_symbol=symbol, underlying_price=underlying_price
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=long_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=long_premium,
            )
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.CALL,
                strike=short_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=short_premium,
            )
        )

        return strategy

    @staticmethod
    def bear_put_spread(
        underlying_price: float,
        long_strike: float,
        short_strike: float,
        expiration: str = "30D",
        long_premium: float = 6.5,
        short_premium: float = 2.8,
        symbol: str = "",
    ) -> MultiLegStrategy:
        """
        Build a bear put spread strategy.

        Structure: Buy higher strike put + Sell lower strike put

        Returns:
            MultiLegStrategy object
        """
        strategy = MultiLegStrategy(
            name="Bear Put Spread", underlying_symbol=symbol, underlying_price=underlying_price
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=long_strike,
                expiration=expiration,
                position_side=PositionSide.LONG,
                quantity=1,
                premium=long_premium,
            )
        )

        strategy.add_leg(
            OptionLeg(
                option_type=OptionType.PUT,
                strike=short_strike,
                expiration=expiration,
                position_side=PositionSide.SHORT,
                quantity=1,
                premium=short_premium,
            )
        )

        return strategy


if __name__ == "__main__":
    # Example usage
    print("=== Options Strategy Builder Examples ===\n")

    # Example 1: Long Straddle
    print("1. Long Straddle on SPY @ $450")
    straddle = StrategyBuilder.long_straddle(
        underlying_price=450, strike=450, call_premium=8.0, put_premium=7.5, symbol="SPY"
    )
    summary = straddle.summary()
    print(f"   Net Premium: ${summary['net_premium']:.2f}")
    print(f"   Max Profit: ${summary['max_profit']:.2f}")
    print(f"   Max Loss: ${summary['max_loss']:.2f}")
    print(f"   Breakevens: {[f'${x:.2f}' for x in summary['breakeven_points']]}")

    # Example 2: Iron Butterfly
    print("\n2. Iron Butterfly on SPY @ $450")
    butterfly = StrategyBuilder.iron_butterfly(
        underlying_price=450,
        atm_strike=450,
        wing_width=10,
        short_call_premium=5.0,
        short_put_premium=4.5,
        long_call_premium=1.0,
        long_put_premium=0.8,
        symbol="SPY",
    )
    summary = butterfly.summary()
    print(f"   Net Premium: ${summary['net_premium']:.2f} (credit)")
    print(f"   Max Profit: ${summary['max_profit']:.2f}")
    print(f"   Max Loss: ${summary['max_loss']:.2f}")
    print(f"   Breakevens: {[f'${x:.2f}' for x in summary['breakeven_points']]}")
    print(f"   Risk/Reward: {summary['risk_reward_ratio']:.2f}")

    # Example 3: Bull Call Spread
    print("\n3. Bull Call Spread on AAPL @ $175")
    bull_spread = StrategyBuilder.bull_call_spread(
        underlying_price=175,
        long_strike=175,
        short_strike=185,
        long_premium=6.0,
        short_premium=2.0,
        symbol="AAPL",
    )
    summary = bull_spread.summary()
    print(f"   Net Premium: ${summary['net_premium']:.2f}")
    print(f"   Max Profit: ${summary['max_profit']:.2f}")
    print(f"   Max Loss: ${summary['max_loss']:.2f}")
    print(f"   Breakeven: ${summary['breakeven_points'][0]:.2f}")
    print(f"   Return on Risk: {(summary['max_profit']/abs(summary['max_loss']))*100:.1f}%")
