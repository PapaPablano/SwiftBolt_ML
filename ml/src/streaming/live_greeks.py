"""Live Greeks calculator for real-time options pricing.

Calculates Greeks in real-time as market data streams in.

Usage:
    from src.streaming.live_greeks import LiveGreeksCalculator
    from src.streaming.websocket_client import WebSocketClient
    
    # Initialize
    greeks_calc = LiveGreeksCalculator(r=0.05, sigma=0.25)
    
    # Set up callback
    def on_greeks_update(symbol, greeks):
        print(f"{symbol}: Delta={greeks['delta']:.4f}")
    
    greeks_calc.set_callback(on_greeks_update)
    
    # Connect to stream
    client = WebSocketClient(url="...")
    client.subscribe(['AAPL'], callback=greeks_calc.on_price_update)
    client.start()
"""

import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class LiveGreeksCalculator:
    """Calculate Greeks in real-time from streaming prices."""
    
    def __init__(
        self,
        r: float = 0.05,
        sigma: float = 0.25,
        update_interval: float = 1.0
    ):
        """Initialize live Greeks calculator.
        
        Args:
            r: Risk-free rate
            sigma: Default volatility (can be overridden per symbol)
            update_interval: Minimum seconds between updates
        """
        self.r = r
        self.sigma = sigma
        self.update_interval = update_interval
        
        self.option_specs: Dict[str, Dict] = {}  # {symbol: {K, T, type}}
        self.last_prices: Dict[str, float] = {}
        self.last_update_times: Dict[str, float] = {}
        self.callback: Optional[Callable] = None
        
        logger.info(f"LiveGreeksCalculator initialized: r={r:.2%}, σ={sigma:.2%}")
    
    def add_option(
        self,
        symbol: str,
        K: float,
        T: float,
        option_type: str = 'call',
        sigma: Optional[float] = None
    ):
        """Add option for Greeks tracking.
        
        Args:
            symbol: Underlying symbol
            K: Strike price
            T: Time to maturity (years)
            option_type: 'call' or 'put'
            sigma: Custom volatility (optional)
        """
        self.option_specs[symbol] = {
            'K': K,
            'T': T,
            'type': option_type,
            'sigma': sigma or self.sigma
        }
        
        logger.info(f"Added option: {symbol} {K} {option_type}")
    
    def set_callback(self, callback: Callable[[str, Dict], None]):
        """Set callback for Greeks updates.
        
        Args:
            callback: Function(symbol, greeks_dict)
        """
        self.callback = callback
    
    def on_price_update(self, message):
        """Handle price update from stream.
        
        Args:
            message: StreamMessage object
        """
        import time
        
        symbol = message.symbol
        price = message.price
        
        # Check if we're tracking this symbol
        if symbol not in self.option_specs:
            return
        
        # Rate limiting
        last_update = self.last_update_times.get(symbol, 0)
        if time.time() - last_update < self.update_interval:
            return
        
        # Store price
        self.last_prices[symbol] = price
        self.last_update_times[symbol] = time.time()
        
        # Calculate Greeks
        try:
            greeks = self._calculate_greeks(symbol, price)
            
            if self.callback and greeks:
                self.callback(symbol, greeks)
                
        except Exception as e:
            logger.error(f"Error calculating Greeks for {symbol}: {e}")
    
    def _calculate_greeks(self, symbol: str, S: float) -> Optional[Dict]:
        """Calculate Greeks for current price.
        
        Args:
            symbol: Option symbol
            S: Current underlying price
        
        Returns:
            Dictionary with Greeks
        """
        spec = self.option_specs.get(symbol)
        if not spec:
            return None
        
        try:
            from ..models.options_pricing import BlackScholesModel
        except ImportError:
            from src.models.options_pricing import BlackScholesModel
        
        bs = BlackScholesModel(risk_free_rate=self.r)
        
        pricing = bs.calculate_greeks(
            S=S,
            K=spec['K'],
            T=spec['T'],
            sigma=spec['sigma'],
            option_type=spec['type']
        )
        
        return {
            'price': pricing.theoretical_price,
            'delta': pricing.delta,
            'gamma': pricing.gamma,
            'theta': pricing.theta,
            'vega': pricing.vega,
            'rho': pricing.rho,
            'underlying_price': S
        }
    
    def get_current_greeks(self, symbol: str) -> Optional[Dict]:
        """Get current Greeks for a symbol.
        
        Args:
            symbol: Option symbol
        
        Returns:
            Greeks dictionary or None
        """
        if symbol not in self.last_prices:
            return None
        
        return self._calculate_greeks(symbol, self.last_prices[symbol])


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Live Greeks Calculator - Self Test")
    print("=" * 70)
    
    # Initialize
    calc = LiveGreeksCalculator(r=0.05, sigma=0.25)
    
    # Add options
    print("\n📊 Adding Options...")
    calc.add_option('AAPL', K=150, T=30/365, option_type='call')
    calc.add_option('SPY', K=450, T=60/365, option_type='put')
    
    # Set callback
    def on_update(symbol, greeks):
        print(f"\n{symbol} Greeks Update:")
        print(f"  Underlying: ${greeks['underlying_price']:.2f}")
        print(f"  Option Price: ${greeks['price']:.2f}")
        print(f"  Delta: {greeks['delta']:.4f}")
        print(f"  Gamma: {greeks['gamma']:.4f}")
        print(f"  Theta: {greeks['theta']:.4f}/day")
        print(f"  Vega: {greeks['vega']:.4f}/%")
    
    calc.set_callback(on_update)
    
    # Simulate price updates
    print("\n📊 Simulating Price Updates...")
    
    from dataclasses import dataclass
    
    @dataclass
    class MockMessage:
        symbol: str
        price: float
    
    # Simulate AAPL update
    calc.on_price_update(MockMessage('AAPL', 148.50))
    
    # Simulate SPY update
    import time
    time.sleep(1.1)  # Wait for rate limit
    calc.on_price_update(MockMessage('SPY', 452.75))
    
    # Get current Greeks
    print("\n📊 Current Greeks:")
    aapl_greeks = calc.get_current_greeks('AAPL')
    if aapl_greeks:
        print(f"AAPL Delta: {aapl_greeks['delta']:.4f}")
    
    print("\n" + "=" * 70)
    print("✅ Live Greeks calculator test complete!")
    print("=" * 70)
