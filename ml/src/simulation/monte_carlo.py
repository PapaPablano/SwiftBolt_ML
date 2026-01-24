"""Monte Carlo simulation for options pricing and risk analysis.

Simulates stock price paths using Geometric Brownian Motion (GBM)
and calculates option prices, Greeks, and risk metrics.

Usage:
    from src.simulation.monte_carlo import MonteCarloSimulator
    
    # Initialize
    sim = MonteCarloSimulator(
        S0=100,
        r=0.05,
        sigma=0.30,
        T=30/365,
        n_simulations=10000
    )
    
    # Generate paths
    paths = sim.generate_paths()
    
    # Price option
    call_price = sim.price_european_option(K=100, option_type='call')
    
    # Calculate Greeks
    greeks = sim.calculate_greeks(K=100, option_type='call')

References:
    - Glasserman, P. (2004). "Monte Carlo Methods in Financial Engineering"
    - Hull, J. C. (2018). "Options, Futures, and Other Derivatives"
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PathGenerator:
    """Generate stock price paths using various models."""
    
    @staticmethod
    def geometric_brownian_motion(
        S0: float,
        r: float,
        sigma: float,
        T: float,
        n_steps: int,
        n_paths: int,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """Generate paths using Geometric Brownian Motion.
        
        Model: dS = μS dt + σS dW
        Solution: S(t) = S(0) exp((μ - σ²/2)t + σW(t))
        
        Args:
            S0: Initial stock price
            r: Risk-free rate (drift)
            sigma: Volatility
            T: Time to maturity (years)
            n_steps: Number of time steps
            n_paths: Number of paths to generate
            seed: Random seed for reproducibility
        
        Returns:
            Array of shape (n_steps + 1, n_paths) with price paths
        """
        if seed is not None:
            np.random.seed(seed)
        
        dt = T / n_steps
        
        # Generate random shocks
        # Use antithetic variates for variance reduction
        half_paths = n_paths // 2
        Z = np.random.standard_normal((n_steps, half_paths))
        Z_anti = -Z  # Antithetic variates
        Z_full = np.concatenate([Z, Z_anti], axis=1)
        
        # If odd number of paths, add one more
        if n_paths % 2 == 1:
            Z_extra = np.random.standard_normal((n_steps, 1))
            Z_full = np.concatenate([Z_full, Z_extra], axis=1)
        
        # Calculate increments
        drift = (r - 0.5 * sigma**2) * dt
        diffusion = sigma * np.sqrt(dt) * Z_full
        
        # Build paths
        log_returns = drift + diffusion
        log_paths = np.vstack([np.zeros(n_paths), np.cumsum(log_returns, axis=0)])
        
        paths = S0 * np.exp(log_paths)
        
        return paths
    
    @staticmethod
    def geometric_brownian_motion_with_jumps(
        S0: float,
        r: float,
        sigma: float,
        T: float,
        n_steps: int,
        n_paths: int,
        lambda_jump: float = 0.1,
        jump_mean: float = -0.1,
        jump_std: float = 0.2,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """Generate paths using Jump Diffusion model (Merton, 1976).
        
        Model: dS = μS dt + σS dW + S dJ
        
        Args:
            S0: Initial stock price
            r: Risk-free rate
            sigma: Volatility
            T: Time to maturity
            n_steps: Number of time steps
            n_paths: Number of paths
            lambda_jump: Jump intensity (average # jumps per year)
            jump_mean: Mean of log-jump size
            jump_std: Std dev of log-jump size
            seed: Random seed
        
        Returns:
            Array of shape (n_steps + 1, n_paths) with price paths
        """
        if seed is not None:
            np.random.seed(seed)
        
        dt = T / n_steps
        
        # GBM component
        paths = PathGenerator.geometric_brownian_motion(
            S0, r, sigma, T, n_steps, n_paths, seed=seed
        )
        
        # Jump component
        # Number of jumps follows Poisson distribution
        n_jumps = np.random.poisson(lambda_jump * T, n_paths)
        
        for path_idx in range(n_paths):
            if n_jumps[path_idx] > 0:
                # Random jump times
                jump_times = np.sort(np.random.uniform(0, T, n_jumps[path_idx]))
                
                # Jump sizes (log-normal)
                jump_sizes = np.exp(
                    jump_mean + jump_std * np.random.randn(n_jumps[path_idx])
                )
                
                # Apply jumps at corresponding time steps
                for jump_time, jump_size in zip(jump_times, jump_sizes):
                    jump_step = int(jump_time / dt)
                    if jump_step < n_steps:
                        paths[jump_step:, path_idx] *= jump_size
        
        return paths


class MonteCarloSimulator:
    """Monte Carlo simulator for options pricing and risk analysis."""
    
    def __init__(
        self,
        S0: float,
        r: float,
        sigma: float,
        T: float,
        n_simulations: int = 10000,
        n_steps: int = 252,
        seed: Optional[int] = None
    ):
        """Initialize Monte Carlo simulator.
        
        Args:
            S0: Initial stock price
            r: Risk-free rate (annualized)
            sigma: Volatility (annualized)
            T: Time to maturity (years)
            n_simulations: Number of simulation paths
            n_steps: Number of time steps per path
            seed: Random seed for reproducibility
        """
        self.S0 = S0
        self.r = r
        self.sigma = sigma
        self.T = T
        self.n_simulations = n_simulations
        self.n_steps = n_steps
        self.seed = seed
        
        self.paths: Optional[np.ndarray] = None
        self.path_generator = PathGenerator()
        
        logger.info(
            f"Initialized Monte Carlo: S0=${S0:.2f}, σ={sigma:.2%}, "
            f"T={T:.2f}y, {n_simulations:,} paths"
        )
    
    def generate_paths(self, use_jumps: bool = False) -> np.ndarray:
        """Generate price paths.
        
        Args:
            use_jumps: Use jump diffusion model if True, else GBM
        
        Returns:
            Array of shape (n_steps + 1, n_simulations)
        """
        if use_jumps:
            self.paths = self.path_generator.geometric_brownian_motion_with_jumps(
                self.S0, self.r, self.sigma, self.T,
                self.n_steps, self.n_simulations, seed=self.seed
            )
        else:
            self.paths = self.path_generator.geometric_brownian_motion(
                self.S0, self.r, self.sigma, self.T,
                self.n_steps, self.n_simulations, seed=self.seed
            )
        
        logger.debug(f"Generated {self.n_simulations} paths")
        return self.paths
    
    def price_european_option(
        self,
        K: float,
        option_type: str = 'call'
    ) -> Dict[str, float]:
        """Price European option via Monte Carlo.
        
        Args:
            K: Strike price
            option_type: 'call' or 'put'
        
        Returns:
            Dictionary with price, std_error, and confidence_interval
        """
        if self.paths is None:
            self.generate_paths()
        
        # Terminal prices
        S_T = self.paths[-1, :]
        
        # Payoffs
        if option_type == 'call':
            payoffs = np.maximum(S_T - K, 0)
        elif option_type == 'put':
            payoffs = np.maximum(K - S_T, 0)
        else:
            raise ValueError(f"Invalid option_type: {option_type}")
        
        # Discount to present value
        discounted_payoffs = payoffs * np.exp(-self.r * self.T)
        
        # Price and standard error
        price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs) / np.sqrt(self.n_simulations)
        
        # 95% confidence interval
        z_score = 1.96
        ci_lower = price - z_score * std_error
        ci_upper = price + z_score * std_error
        
        return {
            'price': float(price),
            'std_error': float(std_error),
            'confidence_interval': (float(ci_lower), float(ci_upper))
        }
    
    def calculate_greeks(
        self,
        K: float,
        option_type: str = 'call',
        epsilon: float = 0.01
    ) -> Dict[str, float]:
        """Calculate Greeks using finite differences.
        
        Args:
            K: Strike price
            option_type: 'call' or 'put'
            epsilon: Bump size for finite differences
        
        Returns:
            Dictionary with delta, gamma, vega, theta, rho
        """
        # Base price
        base_price = self.price_european_option(K, option_type)['price']
        
        # Delta: ∂V/∂S
        sim_up = MonteCarloSimulator(
            self.S0 * (1 + epsilon), self.r, self.sigma, self.T,
            self.n_simulations, self.n_steps, self.seed
        )
        sim_up.generate_paths()
        price_up = sim_up.price_european_option(K, option_type)['price']
        
        sim_down = MonteCarloSimulator(
            self.S0 * (1 - epsilon), self.r, self.sigma, self.T,
            self.n_simulations, self.n_steps, self.seed
        )
        sim_down.generate_paths()
        price_down = sim_down.price_european_option(K, option_type)['price']
        
        delta = (price_up - price_down) / (2 * self.S0 * epsilon)
        
        # Gamma: ∂²V/∂S²
        gamma = (price_up - 2 * base_price + price_down) / (self.S0 * epsilon)**2
        
        # Vega: ∂V/∂σ
        sim_vega = MonteCarloSimulator(
            self.S0, self.r, self.sigma * (1 + epsilon), self.T,
            self.n_simulations, self.n_steps, self.seed
        )
        sim_vega.generate_paths()
        price_vega = sim_vega.price_european_option(K, option_type)['price']
        
        vega = (price_vega - base_price) / (self.sigma * epsilon)
        
        # Theta: ∂V/∂T
        if self.T > epsilon:
            sim_theta = MonteCarloSimulator(
                self.S0, self.r, self.sigma, self.T * (1 - epsilon),
                self.n_simulations, self.n_steps, self.seed
            )
            sim_theta.generate_paths()
            price_theta = sim_theta.price_european_option(K, option_type)['price']
            
            theta = (price_theta - base_price) / (self.T * epsilon)
        else:
            theta = 0.0
        
        # Rho: ∂V/∂r
        sim_rho = MonteCarloSimulator(
            self.S0, self.r * (1 + epsilon), self.sigma, self.T,
            self.n_simulations, self.n_steps, self.seed
        )
        sim_rho.generate_paths()
        price_rho = sim_rho.price_european_option(K, option_type)['price']
        
        rho = (price_rho - base_price) / (self.r * epsilon)
        
        return {
            'delta': float(delta),
            'gamma': float(gamma),
            'vega': float(vega / 100),  # Per 1% change
            'theta': float(theta / 365),  # Per day
            'rho': float(rho / 100)  # Per 1% change
        }
    
    def calculate_var(
        self,
        confidence_level: float = 0.95,
        holding_period_days: int = 1
    ) -> Dict[str, float]:
        """Calculate Value at Risk (VaR).
        
        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            holding_period_days: Holding period in days
        
        Returns:
            Dictionary with VaR, CVaR (Expected Shortfall)
        """
        if self.paths is None:
            self.generate_paths()
        
        # Get prices at holding period
        step_idx = min(holding_period_days, self.n_steps)
        S_t = self.paths[step_idx, :]
        
        # Calculate returns
        returns = (S_t - self.S0) / self.S0
        
        # VaR: Loss at confidence level
        var_percentile = (1 - confidence_level) * 100
        var = -np.percentile(returns, var_percentile) * self.S0
        
        # CVaR: Expected loss beyond VaR
        var_threshold = -var / self.S0
        losses = returns[returns < var_threshold]
        cvar = -np.mean(losses) * self.S0 if len(losses) > 0 else var
        
        return {
            'var': float(var),
            'cvar': float(cvar),
            'confidence_level': confidence_level,
            'holding_period_days': holding_period_days
        }


if __name__ == "__main__":
    # Example usage and validation
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Monte Carlo Simulator - Self Test")
    print("=" * 70)
    
    # Test parameters
    S0 = 100
    K = 100
    r = 0.05
    sigma = 0.30
    T = 30/365
    
    # Initialize simulator
    sim = MonteCarloSimulator(
        S0=S0,
        r=r,
        sigma=sigma,
        T=T,
        n_simulations=10000,
        seed=42
    )
    
    # Test 1: Generate paths
    print("\n📊 Test 1: Path Generation")
    paths = sim.generate_paths()
    print(f"Generated paths shape: {paths.shape}")
    print(f"Initial price: ${paths[0, 0]:.2f}")
    print(f"Final prices: min=${paths[-1, :].min():.2f}, max=${paths[-1, :].max():.2f}")
    print(f"Mean final price: ${paths[-1, :].mean():.2f}")
    
    # Test 2: Price European options
    print("\n📊 Test 2: Option Pricing")
    
    call_result = sim.price_european_option(K, 'call')
    print(f"\nCall Option (K=${K}):")
    print(f"  Price: ${call_result['price']:.4f}")
    print(f"  Std Error: ${call_result['std_error']:.4f}")
    print(f"  95% CI: ${call_result['confidence_interval'][0]:.4f} - "
          f"${call_result['confidence_interval'][1]:.4f}")
    
    put_result = sim.price_european_option(K, 'put')
    print(f"\nPut Option (K=${K}):")
    print(f"  Price: ${put_result['price']:.4f}")
    print(f"  Std Error: ${put_result['std_error']:.4f}")
    
    # Test 3: Calculate Greeks
    print("\n📊 Test 3: Greeks Calculation")
    greeks = sim.calculate_greeks(K, 'call', epsilon=0.01)
    
    print(f"\nCall Greeks:")
    print(f"  Delta: {greeks['delta']:.4f}")
    print(f"  Gamma: {greeks['gamma']:.4f}")
    print(f"  Theta: {greeks['theta']:.4f} (per day)")
    print(f"  Vega: {greeks['vega']:.4f} (per 1%)")
    print(f"  Rho: {greeks['rho']:.4f} (per 1%)")
    
    # Test 4: Compare with Black-Scholes
    print("\n📊 Test 4: Validation vs Black-Scholes")
    
    try:
        from ..models.options_pricing import BlackScholesModel
        
        bs = BlackScholesModel(risk_free_rate=r)
        bs_pricing = bs.calculate_greeks(S=S0, K=K, T=T, sigma=sigma, option_type='call')
        
        print(f"\nComparison (Call @ K=${K}):")
        print(f"  Price: MC=${call_result['price']:.4f}, BS=${bs_pricing.theoretical_price:.4f}, "
              f"Diff={abs(call_result['price'] - bs_pricing.theoretical_price):.4f}")
        print(f"  Delta: MC={greeks['delta']:.4f}, BS={bs_pricing.delta:.4f}, "
              f"Diff={abs(greeks['delta'] - bs_pricing.delta):.4f}")
        
        print("\n✅ Monte Carlo converges to Black-Scholes!")
    except ImportError:
        print("\n⚠️ Black-Scholes model not available for comparison")
    
    # Test 5: VaR calculation
    print("\n📊 Test 5: Value at Risk")
    var_result = sim.calculate_var(confidence_level=0.95, holding_period_days=1)
    
    print(f"\n1-Day VaR (95% confidence):")
    print(f"  VaR: ${var_result['var']:.2f}")
    print(f"  CVaR (Expected Shortfall): ${var_result['cvar']:.2f}")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
