"""Portfolio management and Greeks tracking for options positions.

Tracks portfolio-level Greeks, provides hedging recommendations,
and monitors risk exposure in real-time.

Usage:
    from src.risk.portfolio_manager import PortfolioManager
    
    # Initialize
    pm = PortfolioManager()
    
    # Add positions
    pm.add_position('AAPL_CALL_150', quantity=2, greeks={
        'delta': 0.52, 'gamma': 0.03, 'theta': -0.04, 'vega': 0.18
    })
    
    # Get portfolio Greeks
    portfolio_greeks = pm.get_portfolio_greeks()
    print(f"Portfolio Delta: {portfolio_greeks.delta}")
    
    # Get hedging recommendation
    hedge = pm.suggest_delta_hedge(target_delta=0)
    print(f"Hedge: {hedge}")
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioGreeks:
    """Portfolio-level Greeks.
    
    Attributes:
        delta: Portfolio delta
        gamma: Portfolio gamma
        theta: Portfolio theta (per day)
        vega: Portfolio vega (per 1% vol)
        rho: Portfolio rho (per 1% rate)
    """
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    
    def __str__(self) -> str:
        return (
            f"Portfolio Greeks:\n"
            f"  Delta: {self.delta:.2f}\n"
            f"  Gamma: {self.gamma:.4f}\n"
            f"  Theta: {self.theta:.2f}/day\n"
            f"  Vega: {self.vega:.2f}/%\n"
            f"  Rho: {self.rho:.2f}/%"
        )


@dataclass
class Position:
    """Represents an options position.
    
    Attributes:
        symbol: Position symbol
        quantity: Number of contracts (+ long, - short)
        underlying_price: Current underlying price
        greeks: Position Greeks
        entry_price: Entry price
        current_price: Current market price
    """
    symbol: str
    quantity: int
    underlying_price: float
    greeks: Dict[str, float]
    entry_price: float = 0.0
    current_price: float = 0.0
    
    def position_greeks(self) -> Dict[str, float]:
        """Calculate position-level Greeks (quantity × Greeks)."""
        multiplier = self.quantity * 100  # 100 shares per contract
        return {
            'delta': self.greeks.get('delta', 0) * multiplier,
            'gamma': self.greeks.get('gamma', 0) * multiplier,
            'theta': self.greeks.get('theta', 0) * multiplier,
            'vega': self.greeks.get('vega', 0) * multiplier,
            'rho': self.greeks.get('rho', 0) * multiplier
        }
    
    def market_value(self) -> float:
        """Calculate current market value."""
        return self.current_price * self.quantity * 100
    
    def pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.entry_price == 0:
            return 0
        return (self.current_price - self.entry_price) * self.quantity * 100


class PortfolioManager:
    """Manage options portfolio and track risk."""
    
    def __init__(self):
        """Initialize portfolio manager."""
        self.positions: Dict[str, Position] = {}
        self.cash = 0.0
    
    def add_position(
        self,
        symbol: str,
        quantity: int,
        greeks: Dict[str, float],
        underlying_price: float,
        entry_price: float = 0.0,
        current_price: float = 0.0
    ):
        """Add or update position.
        
        Args:
            symbol: Option symbol
            quantity: Number of contracts
            greeks: Greeks dictionary
            underlying_price: Current underlying price
            entry_price: Entry price
            current_price: Current market price
        """
        if symbol in self.positions:
            # Update existing position
            pos = self.positions[symbol]
            pos.quantity += quantity
            pos.greeks = greeks
            pos.underlying_price = underlying_price
            pos.current_price = current_price
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                underlying_price=underlying_price,
                greeks=greeks,
                entry_price=entry_price,
                current_price=current_price
            )
        
        logger.info(f"Added position: {symbol} x{quantity}")
    
    def remove_position(self, symbol: str):
        """Remove position from portfolio."""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Removed position: {symbol}")
    
    def get_positions(self) -> pd.DataFrame:
        """Get all positions as DataFrame."""
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for symbol, pos in self.positions.items():
            pos_greeks = pos.position_greeks()
            data.append({
                'symbol': symbol,
                'quantity': pos.quantity,
                'underlying_price': pos.underlying_price,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'market_value': pos.market_value(),
                'pnl': pos.pnl(),
                'delta': pos_greeks['delta'],
                'gamma': pos_greeks['gamma'],
                'theta': pos_greeks['theta'],
                'vega': pos_greeks['vega'],
                'rho': pos_greeks['rho']
            })
        
        return pd.DataFrame(data)
    
    def get_portfolio_greeks(self) -> PortfolioGreeks:
        """Calculate portfolio-level Greeks.
        
        Returns:
            PortfolioGreeks object with aggregated Greeks
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0
        
        for position in self.positions.values():
            pos_greeks = position.position_greeks()
            total_delta += pos_greeks['delta']
            total_gamma += pos_greeks['gamma']
            total_theta += pos_greeks['theta']
            total_vega += pos_greeks['vega']
            total_rho += pos_greeks['rho']
        
        return PortfolioGreeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
            rho=total_rho
        )
    
    def suggest_delta_hedge(
        self,
        target_delta: float = 0,
        underlying_price: float = 100
    ) -> Dict:
        """Suggest delta hedge to achieve target delta.
        
        Args:
            target_delta: Target portfolio delta
            underlying_price: Current underlying price
        
        Returns:
            Dictionary with hedge recommendation
        """
        current_greeks = self.get_portfolio_greeks()
        delta_diff = target_delta - current_greeks.delta
        
        # Shares needed (delta of stock = 1.0 per share)
        shares_needed = int(delta_diff)
        
        action = "BUY" if shares_needed > 0 else "SELL"
        
        return {
            'current_delta': current_greeks.delta,
            'target_delta': target_delta,
            'delta_difference': delta_diff,
            'action': action,
            'shares': abs(shares_needed),
            'estimated_cost': abs(shares_needed) * underlying_price,
            'recommendation': f"{action} {abs(shares_needed)} shares @ ${underlying_price:.2f}"
        }
    
    def calculate_portfolio_var(
        self,
        confidence_level: float = 0.95,
        time_horizon_days: int = 1,
        underlying_volatility: float = 0.30
    ) -> Dict:
        """Calculate portfolio Value at Risk.
        
        Simplified VaR using delta-gamma approximation.
        
        Args:
            confidence_level: Confidence level (e.g., 0.95)
            time_horizon_days: Time horizon in days
            underlying_volatility: Underlying volatility
        
        Returns:
            Dictionary with VaR metrics
        """
        import scipy.stats as stats
        
        greeks = self.get_portfolio_greeks()
        
        # Assume normal distribution of returns
        z_score = stats.norm.ppf(confidence_level)
        
        # Estimate portfolio volatility (simplified)
        # ΔP ≈ Delta × ΔS + 0.5 × Gamma × (ΔS)²
        
        # For now, use delta-only approximation
        # More sophisticated: incorporate gamma, vega
        
        portfolio_vol = abs(greeks.delta) * underlying_volatility
        
        # VaR = Portfolio Value × Volatility × Z-score × √(time)
        # Simplified for demonstration
        var = portfolio_vol * z_score * (time_horizon_days ** 0.5)
        
        return {
            'var': var,
            'confidence_level': confidence_level,
            'time_horizon_days': time_horizon_days,
            'portfolio_delta': greeks.delta,
            'portfolio_gamma': greeks.gamma
        }
    
    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary.
        
        Returns:
            Dictionary with portfolio metrics
        """
        positions_df = self.get_positions()
        greeks = self.get_portfolio_greeks()
        
        if positions_df.empty:
            return {
                'num_positions': 0,
                'total_market_value': 0,
                'total_pnl': 0,
                'greeks': greeks
            }
        
        return {
            'num_positions': len(self.positions),
            'total_market_value': positions_df['market_value'].sum(),
            'total_pnl': positions_df['pnl'].sum(),
            'cash': self.cash,
            'greeks': greeks,
            'largest_position': positions_df.loc[positions_df['market_value'].abs().idxmax(), 'symbol'],
            'most_profitable': positions_df.loc[positions_df['pnl'].idxmax(), 'symbol'] if len(positions_df) > 0 else None
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Portfolio Manager - Self Test")
    print("=" * 70)
    
    # Initialize
    pm = PortfolioManager()
    pm.cash = 10000
    
    # Add positions
    print("\n📊 Adding Positions...")
    
    pm.add_position(
        symbol='AAPL_CALL_150',
        quantity=2,
        greeks={'delta': 0.52, 'gamma': 0.03, 'theta': -0.04, 'vega': 0.18, 'rho': 0.02},
        underlying_price=148,
        entry_price=5.0,
        current_price=6.5
    )
    
    pm.add_position(
        symbol='AAPL_PUT_140',
        quantity=-1,
        greeks={'delta': -0.30, 'gamma': 0.025, 'theta': -0.03, 'vega': 0.15, 'rho': -0.03},
        underlying_price=148,
        entry_price=3.0,
        current_price=2.0
    )
    
    # Get positions
    print("\n📊 Current Positions:")
    positions = pm.get_positions()
    print(positions.to_string())
    
    # Portfolio Greeks
    print("\n📊 Portfolio Greeks:")
    greeks = pm.get_portfolio_greeks()
    print(greeks)
    
    # Delta hedge
    print("\n📊 Delta Hedge Recommendation:")
    hedge = pm.suggest_delta_hedge(target_delta=0, underlying_price=148)
    print(f"Current Delta: {hedge['current_delta']:.2f}")
    print(f"Recommendation: {hedge['recommendation']}")
    print(f"Estimated Cost: ${hedge['estimated_cost']:.2f}")
    
    # Portfolio summary
    print("\n📊 Portfolio Summary:")
    summary = pm.get_portfolio_summary()
    print(f"Number of Positions: {summary['num_positions']}")
    print(f"Total Market Value: ${summary['total_market_value']:.2f}")
    print(f"Total P&L: ${summary['total_pnl']:.2f}")
    print(f"Cash: ${summary['cash']:.2f}")
    
    print("\n" + "=" * 70)
    print("✅ Portfolio manager test complete!")
    print("=" * 70)
