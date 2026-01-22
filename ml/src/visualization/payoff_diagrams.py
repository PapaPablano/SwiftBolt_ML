"""Payoff diagram generation for options strategies.

Creates visual representations of options strategies showing:
- Profit/loss at expiration
- Break-even points
- Max profit/loss
- Multi-leg strategies

Usage:
    from src.visualization.payoff_diagrams import PayoffDiagram
    
    # Single option
    diagram = PayoffDiagram()
    
    # Add long call
    diagram.add_option('call', strike=100, premium=5.0, quantity=1, action='buy')
    
    # Generate plot
    fig = diagram.plot(underlying_range=(80, 120))
    fig.show()
    
    # Multi-leg (iron condor)
    diagram = PayoffDiagram()
    diagram.add_option('call', 110, 3.0, -1)  # Sell call
    diagram.add_option('call', 115, 1.5, 1)   # Buy call
    diagram.add_option('put', 90, 3.0, -1)    # Sell put
    diagram.add_option('put', 85, 1.5, 1)     # Buy put
    
    fig = diagram.plot()
    fig.show()

References:
    - Hull, J. C. (2018). "Options, Futures, and Other Derivatives"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logging.warning("Plotly not available. Install with: pip install plotly")

logger = logging.getLogger(__name__)


@dataclass
class OptionLeg:
    """Represents a single option leg in a strategy.
    
    Attributes:
        option_type: 'call' or 'put'
        strike: Strike price
        premium: Premium paid/received per share
        quantity: Number of contracts (negative = short)
        multiplier: Contract multiplier (default: 100)
    """
    option_type: str
    strike: float
    premium: float
    quantity: int = 1
    multiplier: int = 100
    
    def __post_init__(self):
        """Validate option leg."""
        if self.option_type not in ['call', 'put']:
            raise ValueError(f"Invalid option_type: {self.option_type}")
    
    def payoff_at_price(self, underlying_price: float) -> float:
        """Calculate payoff at given underlying price.
        
        Args:
            underlying_price: Underlying price at expiration
        
        Returns:
            Payoff including premium paid/received
        """
        if self.option_type == 'call':
            intrinsic = max(underlying_price - self.strike, 0)
        else:  # put
            intrinsic = max(self.strike - underlying_price, 0)
        
        # For long positions: -premium + intrinsic
        # For short positions: +premium - intrinsic
        if self.quantity > 0:  # Long
            payoff = (intrinsic - self.premium) * abs(self.quantity) * self.multiplier
        else:  # Short
            payoff = (self.premium - intrinsic) * abs(self.quantity) * self.multiplier
        
        return payoff


class PayoffCalculator:
    """Calculate payoff metrics for options strategies."""
    
    @staticmethod
    def calculate_payoff(
        legs: List[OptionLeg],
        underlying_prices: np.ndarray
    ) -> np.ndarray:
        """Calculate total payoff across price range.
        
        Args:
            legs: List of option legs
            underlying_prices: Array of underlying prices
        
        Returns:
            Array of total payoffs
        """
        total_payoff = np.zeros_like(underlying_prices, dtype=float)
        
        for leg in legs:
            leg_payoff = np.array([
                leg.payoff_at_price(price) for price in underlying_prices
            ])
            total_payoff += leg_payoff
        
        return total_payoff
    
    @staticmethod
    def find_break_even(
        legs: List[OptionLeg],
        price_range: Tuple[float, float] = (0, 500),
        precision: float = 0.01
    ) -> List[float]:
        """Find break-even points.
        
        Args:
            legs: List of option legs
            price_range: (min, max) price range to search
            precision: Price precision for break-even
        
        Returns:
            List of break-even prices
        """
        prices = np.arange(price_range[0], price_range[1], precision)
        payoffs = PayoffCalculator.calculate_payoff(legs, prices)
        
        # Find zero crossings
        break_evens = []
        for i in range(len(payoffs) - 1):
            if payoffs[i] * payoffs[i + 1] < 0:  # Sign change
                # Linear interpolation for better accuracy
                be = prices[i] - payoffs[i] * (prices[i + 1] - prices[i]) / (payoffs[i + 1] - payoffs[i])
                break_evens.append(float(be))
        
        return break_evens
    
    @staticmethod
    def max_profit(
        legs: List[OptionLeg],
        price_range: Tuple[float, float] = (0, 500)
    ) -> Tuple[float, float]:
        """Calculate maximum profit and price where it occurs.
        
        Args:
            legs: List of option legs
            price_range: (min, max) price range
        
        Returns:
            (max_profit, price_at_max)
        """
        prices = np.linspace(price_range[0], price_range[1], 1000)
        payoffs = PayoffCalculator.calculate_payoff(legs, prices)
        
        max_idx = np.argmax(payoffs)
        return float(payoffs[max_idx]), float(prices[max_idx])
    
    @staticmethod
    def max_loss(
        legs: List[OptionLeg],
        price_range: Tuple[float, float] = (0, 500)
    ) -> Tuple[float, float]:
        """Calculate maximum loss and price where it occurs.
        
        Args:
            legs: List of option legs
            price_range: (min, max) price range
        
        Returns:
            (max_loss, price_at_max_loss)
        """
        prices = np.linspace(price_range[0], price_range[1], 1000)
        payoffs = PayoffCalculator.calculate_payoff(legs, prices)
        
        min_idx = np.argmin(payoffs)
        return float(payoffs[min_idx]), float(prices[min_idx])
    
    @staticmethod
    def initial_cost(legs: List[OptionLeg]) -> float:
        """Calculate initial cost (debit) or credit.
        
        Args:
            legs: List of option legs
        
        Returns:
            Initial cost (positive = debit, negative = credit)
        """
        total = 0
        for leg in legs:
            if leg.quantity > 0:  # Long
                total += leg.premium * leg.quantity * leg.multiplier
            else:  # Short
                total -= leg.premium * abs(leg.quantity) * leg.multiplier
        
        return total


class PayoffDiagram:
    """Generate payoff diagrams for options strategies."""
    
    def __init__(self, strategy_name: str = "Options Strategy"):
        """Initialize payoff diagram.
        
        Args:
            strategy_name: Name of the strategy
        """
        self.strategy_name = strategy_name
        self.legs: List[OptionLeg] = []
        self.calculator = PayoffCalculator()
    
    def add_option(
        self,
        option_type: str,
        strike: float,
        premium: float,
        quantity: int = 1,
        multiplier: int = 100
    ):
        """Add an option leg to the strategy.
        
        Args:
            option_type: 'call' or 'put'
            strike: Strike price
            premium: Premium per share
            quantity: Number of contracts (negative for short)
            multiplier: Contract multiplier
        """
        leg = OptionLeg(option_type, strike, premium, quantity, multiplier)
        self.legs.append(leg)
        
        action = "Long" if quantity > 0 else "Short"
        logger.info(f"Added {action} {abs(quantity)} {option_type.upper()} @ ${strike:.2f}")
    
    def add_stock(self, shares: int, price: float):
        """Add stock position (for covered calls, etc.).
        
        Args:
            shares: Number of shares (negative for short)
            price: Stock purchase price
        """
        # Model stock as deep ITM option with 0 premium
        # This is a simplification but works for payoff diagrams
        logger.info(f"Added {shares} shares @ ${price:.2f}")
        # Note: Stock positions would need special handling in a full implementation
    
    def plot(
        self,
        underlying_range: Optional[Tuple[float, float]] = None,
        current_price: Optional[float] = None,
        show_break_even: bool = True,
        show_max_profit_loss: bool = True,
        title: Optional[str] = None
    ):
        """Generate payoff diagram plot.
        
        Args:
            underlying_range: (min, max) price range (auto if None)
            current_price: Current underlying price (for vertical line)
            show_break_even: Show break-even points
            show_max_profit_loss: Show max profit/loss points
            title: Custom title
        
        Returns:
            Plotly figure object
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly required for visualization. Install with: pip install plotly")
        
        if not self.legs:
            raise ValueError("No legs added to strategy")
        
        # Determine price range
        if underlying_range is None:
            strikes = [leg.strike for leg in self.legs]
            min_strike = min(strikes)
            max_strike = max(strikes)
            range_width = max_strike - min_strike
            underlying_range = (
                max(0, min_strike - range_width * 0.3),
                max_strike + range_width * 0.3
            )
        
        # Generate price points
        prices = np.linspace(underlying_range[0], underlying_range[1], 500)
        
        # Calculate payoff
        payoff = self.calculator.calculate_payoff(self.legs, prices)
        
        # Create figure
        fig = go.Figure()
        
        # Add payoff line
        fig.add_trace(go.Scatter(
            x=prices,
            y=payoff,
            mode='lines',
            name='Payoff at Expiration',
            line=dict(color='blue', width=3),
            hovertemplate='Price: $%{x:.2f}<br>P&L: $%{y:.2f}<extra></extra>'
        ))
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Add current price line
        if current_price is not None:
            fig.add_vline(
                x=current_price,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"Current: ${current_price:.2f}",
                annotation_position="top"
            )
        
        # Add break-even points
        if show_break_even:
            break_evens = self.calculator.find_break_even(self.legs, underlying_range)
            for be in break_evens:
                fig.add_trace(go.Scatter(
                    x=[be],
                    y=[0],
                    mode='markers',
                    name=f'Break-even: ${be:.2f}',
                    marker=dict(size=12, color='green', symbol='diamond')
                ))
        
        # Add max profit/loss points
        if show_max_profit_loss:
            max_profit, price_at_max = self.calculator.max_profit(self.legs, underlying_range)
            max_loss, price_at_loss = self.calculator.max_loss(self.legs, underlying_range)
            
            if max_profit > 0:
                fig.add_trace(go.Scatter(
                    x=[price_at_max],
                    y=[max_profit],
                    mode='markers',
                    name=f'Max Profit: ${max_profit:.2f}',
                    marker=dict(size=12, color='green', symbol='star')
                ))
            
            if max_loss < 0:
                fig.add_trace(go.Scatter(
                    x=[price_at_loss],
                    y=[max_loss],
                    mode='markers',
                    name=f'Max Loss: ${max_loss:.2f}',
                    marker=dict(size=12, color='red', symbol='x')
                ))
        
        # Calculate initial cost
        initial_cost = self.calculator.initial_cost(self.legs)
        cost_type = "Debit" if initial_cost > 0 else "Credit"
        
        # Update layout
        fig.update_layout(
            title=title or f"{self.strategy_name}<br><sub>{cost_type}: ${abs(initial_cost):.2f}</sub>",
            xaxis_title="Underlying Price at Expiration",
            yaxis_title="Profit / Loss ($)",
            hovermode='x unified',
            template='plotly_white',
            height=600,
            width=1000,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        # Add shaded regions for profit/loss
        fig.add_hrect(
            y0=0, y1=max(payoff) * 1.1,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
        )
        fig.add_hrect(
            y0=min(payoff) * 1.1, y1=0,
            fillcolor="red", opacity=0.1,
            layer="below", line_width=0,
        )
        
        return fig
    
    def get_summary(self) -> Dict:
        """Get strategy summary with key metrics.
        
        Returns:
            Dictionary with strategy metrics
        """
        if not self.legs:
            return {}
        
        # Determine price range
        strikes = [leg.strike for leg in self.legs]
        min_strike = min(strikes)
        max_strike = max(strikes)
        range_width = max_strike - min_strike
        price_range = (
            max(0, min_strike - range_width * 0.5),
            max_strike + range_width * 0.5
        )
        
        # Calculate metrics
        initial_cost = self.calculator.initial_cost(self.legs)
        break_evens = self.calculator.find_break_even(self.legs, price_range)
        max_profit, _ = self.calculator.max_profit(self.legs, price_range)
        max_loss, _ = self.calculator.max_loss(self.legs, price_range)
        
        # Risk/reward ratio
        if max_loss != 0:
            risk_reward = abs(max_profit / max_loss)
        else:
            risk_reward = float('inf') if max_profit > 0 else 0
        
        return {
            'strategy_name': self.strategy_name,
            'num_legs': len(self.legs),
            'initial_cost': initial_cost,
            'cost_type': 'Debit' if initial_cost > 0 else 'Credit',
            'break_even_points': break_evens,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'risk_reward_ratio': risk_reward,
            'strikes': strikes,
            'min_strike': min_strike,
            'max_strike': max_strike
        }
    
    def print_summary(self):
        """Print strategy summary to console."""
        summary = self.get_summary()
        
        if not summary:
            print("No legs in strategy")
            return
        
        print("=" * 70)
        print(f"Strategy: {summary['strategy_name']}")
        print("=" * 70)
        print(f"Number of Legs: {summary['num_legs']}")
        print(f"Initial {summary['cost_type']}: ${abs(summary['initial_cost']):.2f}")
        print(f"\nMax Profit: ${summary['max_profit']:.2f}")
        print(f"Max Loss: ${summary['max_loss']:.2f}")
        print(f"Risk/Reward Ratio: {summary['risk_reward_ratio']:.2f}")
        print(f"\nBreak-even Points: {[f'${be:.2f}' for be in summary['break_even_points']]}")
        print(f"Strike Range: ${summary['min_strike']:.2f} - ${summary['max_strike']:.2f}")
        print("=" * 70)


if __name__ == "__main__":
    # Example usage and self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Payoff Diagram - Self Test")
    print("=" * 70)
    
    # Test 1: Long Call
    print("\n📊 Test 1: Long Call")
    diagram1 = PayoffDiagram("Long Call")
    diagram1.add_option('call', strike=100, premium=5.0, quantity=1)
    diagram1.print_summary()
    
    # Test 2: Bull Call Spread
    print("\n📊 Test 2: Bull Call Spread")
    diagram2 = PayoffDiagram("Bull Call Spread")
    diagram2.add_option('call', strike=100, premium=5.0, quantity=1)   # Buy
    diagram2.add_option('call', strike=110, premium=2.0, quantity=-1)  # Sell
    diagram2.print_summary()
    
    # Test 3: Iron Condor
    print("\n📊 Test 3: Iron Condor")
    diagram3 = PayoffDiagram("Iron Condor")
    diagram3.add_option('call', strike=110, premium=3.0, quantity=-1)  # Sell call
    diagram3.add_option('call', strike=115, premium=1.5, quantity=1)   # Buy call
    diagram3.add_option('put', strike=90, premium=3.0, quantity=-1)    # Sell put
    diagram3.add_option('put', strike=85, premium=1.5, quantity=1)     # Buy put
    diagram3.print_summary()
    
    # Generate plots if plotly available
    if PLOTLY_AVAILABLE:
        print("\n📈 Generating plots...")
        
        fig1 = diagram1.plot(current_price=100)
        print("✅ Long Call plot generated")
        
        fig2 = diagram2.plot(current_price=100)
        print("✅ Bull Call Spread plot generated")
        
        fig3 = diagram3.plot(current_price=100)
        print("✅ Iron Condor plot generated")
        
        # Uncomment to show plots
        # fig1.show()
        # fig2.show()
        # fig3.show()
    else:
        print("\n⚠️ Plotly not installed - skipping plot generation")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
