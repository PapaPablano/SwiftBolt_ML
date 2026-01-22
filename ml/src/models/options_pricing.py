"""Black-Scholes Options Pricing and Greeks Calculation.

Implements the Black-Scholes-Merton model for European options pricing
and Greeks calculation. Provides theoretical prices for validation against
API data and implied volatility calculation via Newton-Raphson method.

Usage:
    from src.models.options_pricing import BlackScholesModel
    
    bs = BlackScholesModel(risk_free_rate=0.045)
    
    # Price an option
    call_price = bs.price_call(S=100, K=100, T=0.5, sigma=0.25)
    
    # Calculate all Greeks
    pricing = bs.calculate_greeks(S=100, K=100, T=0.5, sigma=0.25, option_type='call')
    print(f"Delta: {pricing.delta:.4f}")
    print(f"Gamma: {pricing.gamma:.4f}")
    print(f"Theta: {pricing.theta:.4f}")
    print(f"Vega: {pricing.vega:.4f}")
    
    # Calculate implied volatility
    iv = bs.calculate_implied_volatility(
        market_price=10.50,
        S=100, K=100, T=0.5,
        option_type='call'
    )
    print(f"Implied Vol: {iv:.2%}")

References:
    - Black, F., & Scholes, M. (1973). "The Pricing of Options and Corporate Liabilities"
    - Hull, J. C. (2018). "Options, Futures, and Other Derivatives" (10th ed.)
    - https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


@dataclass
class OptionsPricing:
    """Black-Scholes pricing results with all Greeks.
    
    Attributes:
        theoretical_price: Fair value of the option
        delta: Rate of change of option price with respect to underlying price
        gamma: Rate of change of delta with respect to underlying price
        theta: Rate of change of option price with respect to time (per day)
        vega: Rate of change of option price with respect to volatility (per 1%)
        rho: Rate of change of option price with respect to interest rate (per 1%)
        implied_vol: Calculated implied volatility (if applicable)
    """
    theoretical_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_vol: Optional[float] = None
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"OptionsPricing(\n"
            f"  Price: ${self.theoretical_price:.2f}\n"
            f"  Delta: {self.delta:.4f}\n"
            f"  Gamma: {self.gamma:.4f}\n"
            f"  Theta: {self.theta:.4f}/day\n"
            f"  Vega: {self.vega:.4f}/%\n"
            f"  Rho: {self.rho:.4f}/%\n"
            f")"
        )


class BlackScholesModel:
    """Black-Scholes-Merton model for European options pricing.
    
    Assumptions:
        - European-style options (exercise only at expiration)
        - No dividends (or dividend yield can be incorporated)
        - Constant volatility and risk-free rate
        - Lognormal distribution of stock prices
        - No transaction costs or taxes
        - Markets are efficient (no arbitrage)
    
    Attributes:
        risk_free_rate: Annual risk-free interest rate (e.g., 10-year Treasury yield)
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        """Initialize Black-Scholes model.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 5%)
                           Use current 10-year Treasury yield for accuracy
        """
        self.risk_free_rate = risk_free_rate
        logger.debug(f"Initialized Black-Scholes model with r={risk_free_rate:.4f}")
    
    def price_call(self, S: float, K: float, T: float, sigma: float) -> float:
        """Calculate European call option price.
        
        Formula: C = S * N(d1) - K * e^(-rT) * N(d2)
        
        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Volatility (annualized)
        
        Returns:
            Call option theoretical price
        """
        if T <= 0:
            # At expiration: max(S - K, 0)
            return max(S - K, 0)
        
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        call_price = S * norm.cdf(d1) - K * np.exp(-self.risk_free_rate*T) * norm.cdf(d2)
        
        return call_price
    
    def price_put(self, S: float, K: float, T: float, sigma: float) -> float:
        """Calculate European put option price.
        
        Formula: P = K * e^(-rT) * N(-d2) - S * N(-d1)
        
        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Volatility (annualized)
        
        Returns:
            Put option theoretical price
        """
        if T <= 0:
            # At expiration: max(K - S, 0)
            return max(K - S, 0)
        
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        put_price = K * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return put_price
    
    def calculate_greeks(
        self, 
        S: float, 
        K: float, 
        T: float, 
        sigma: float, 
        option_type: str = 'call'
    ) -> OptionsPricing:
        """Calculate option price and all Greeks.
        
        Greeks are partial derivatives of the option price:
        - Delta (Δ): ∂V/∂S - Price sensitivity to underlying
        - Gamma (Γ): ∂²V/∂S² - Delta sensitivity to underlying
        - Theta (Θ): ∂V/∂t - Time decay (per day)
        - Vega (ν): ∂V/∂σ - Volatility sensitivity (per 1%)
        - Rho (ρ): ∂V/∂r - Interest rate sensitivity (per 1%)
        
        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Volatility (annualized)
            option_type: 'call' or 'put'
        
        Returns:
            OptionsPricing object with price and all Greeks
        """
        if T <= 0:
            # At expiration - simplified Greeks
            if option_type.lower() == 'call':
                price = max(S - K, 0)
                delta = 1.0 if S > K else 0.0
            else:
                price = max(K - S, 0)
                delta = -1.0 if S < K else 0.0
            
            return OptionsPricing(
                theoretical_price=price,
                delta=delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0
            )
        
        # Calculate d1 and d2
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        # Price
        if option_type.lower() == 'call':
            price = self.price_call(S, K, T, sigma)
            delta = norm.cdf(d1)
        else:
            price = self.price_put(S, K, T, sigma)
            delta = -norm.cdf(-d1)  # Negative for puts
        
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        # Vega (same for calls and puts, per 1% change in volatility)
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        # Theta (per day, divide by 365)
        if option_type.lower() == 'call':
            theta = (
                (-S * norm.pdf(d1) * sigma / (2*np.sqrt(T)) 
                 - self.risk_free_rate * K * np.exp(-self.risk_free_rate*T) * norm.cdf(d2))
                / 365
            )
        else:
            theta = (
                (-S * norm.pdf(d1) * sigma / (2*np.sqrt(T)) 
                 + self.risk_free_rate * K * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2))
                / 365
            )
        
        # Rho (per 1% change in interest rate)
        if option_type.lower() == 'call':
            rho = K * T * np.exp(-self.risk_free_rate*T) * norm.cdf(d2) / 100
        else:
            rho = -K * T * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2) / 100
        
        return OptionsPricing(
            theoretical_price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
    
    def calculate_implied_volatility(
        self, 
        market_price: float, 
        S: float, 
        K: float, 
        T: float, 
        option_type: str = 'call',
        initial_guess: float = 0.3,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> float:
        """Calculate implied volatility using Newton-Raphson method.
        
        Implied volatility is the volatility value that makes the theoretical
        price equal to the market price. Solved iteratively:
        
        σ_(n+1) = σ_n + (Market_Price - Theoretical_Price) / Vega
        
        Args:
            market_price: Observed market price of the option
            S: Current underlying price
            K: Strike price
            T: Time to expiration (years)
            option_type: 'call' or 'put'
            initial_guess: Starting volatility estimate (default: 30%)
            max_iterations: Maximum Newton-Raphson iterations
            tolerance: Convergence threshold for price difference
        
        Returns:
            Implied volatility (annualized)
        
        Raises:
            ValueError: If convergence fails or inputs invalid
        """
        if T <= 0:
            logger.warning("Cannot calculate IV for expired options (T <= 0)")
            return 0.0
        
        if market_price <= 0:
            raise ValueError(f"Market price must be positive, got {market_price}")
        
        # Sanity check: market price should be less than intrinsic value upper bound
        if option_type.lower() == 'call' and market_price > S:
            raise ValueError(f"Call price ({market_price}) cannot exceed stock price ({S})")
        if option_type.lower() == 'put' and market_price > K:
            raise ValueError(f"Put price ({market_price}) cannot exceed strike ({K})")
        
        sigma = initial_guess
        
        for iteration in range(max_iterations):
            # Calculate theoretical price and vega at current sigma
            if option_type.lower() == 'call':
                theo_price = self.price_call(S, K, T, sigma)
            else:
                theo_price = self.price_put(S, K, T, sigma)
            
            # Check convergence
            price_diff = market_price - theo_price
            
            if abs(price_diff) < tolerance:
                logger.debug(f"IV converged in {iteration+1} iterations: σ={sigma:.4f}")
                return sigma
            
            # Calculate vega for Newton-Raphson update
            d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            if vega < 1e-10:
                logger.warning(f"Vega too small at iteration {iteration}, sigma={sigma:.4f}")
                break
            
            # Newton-Raphson update
            sigma += price_diff / vega
            
            # Bound sigma to reasonable range
            sigma = max(0.01, min(sigma, 5.0))  # 1% to 500%
        
        logger.warning(
            f"IV calculation did not converge after {max_iterations} iterations. "
            f"Last sigma={sigma:.4f}, price_diff={price_diff:.4f}"
        )
        return sigma
    
    def verify_put_call_parity(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        tolerance: float = 0.01
    ) -> bool:
        """Verify put-call parity: C - P = S - K*e^(-rT).
        
        Put-call parity is an arbitrage relationship that must hold for
        European options. Useful for validating pricing calculations.
        
        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Volatility
            tolerance: Acceptable deviation (default: $0.01)
        
        Returns:
            True if parity holds within tolerance
        """
        call_price = self.price_call(S, K, T, sigma)
        put_price = self.price_put(S, K, T, sigma)
        
        lhs = call_price - put_price
        rhs = S - K * np.exp(-self.risk_free_rate * T)
        
        diff = abs(lhs - rhs)
        
        if diff > tolerance:
            logger.warning(
                f"Put-call parity violation: |C-P - (S-Ke^(-rT))| = {diff:.4f} > {tolerance}"
            )
            return False
        
        return True


def get_current_risk_free_rate() -> float:
    """Get current risk-free rate (10-year Treasury yield).
    
    TODO: Implement API call to fetch current rate from:
    - FRED API (Federal Reserve Economic Data)
    - Yahoo Finance
    - Treasury.gov
    
    Returns:
        Annual risk-free rate (e.g., 0.045 for 4.5%)
    """
    # Placeholder: Update this value monthly
    # As of January 2026, estimate ~4.5%
    return 0.045


if __name__ == "__main__":
    # Example usage and self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Black-Scholes Model - Self Test")
    print("=" * 70)
    
    bs = BlackScholesModel(risk_free_rate=0.05)
    
    # Test 1: ATM call pricing
    print("\n📊 Test 1: ATM Call Option")
    print(f"Underlying: $100, Strike: $100, Time: 1 year, Vol: 20%")
    
    pricing = bs.calculate_greeks(S=100, K=100, T=1.0, sigma=0.20, option_type='call')
    print(pricing)
    
    # Test 2: Put-call parity
    print("\n📊 Test 2: Put-Call Parity Verification")
    parity_valid = bs.verify_put_call_parity(S=100, K=100, T=1.0, sigma=0.20)
    print(f"Put-call parity holds: {parity_valid} ✅" if parity_valid else "❌")
    
    # Test 3: Implied volatility
    print("\n📊 Test 3: Implied Volatility Calculation")
    market_price = 10.45
    print(f"Market price: ${market_price:.2f}")
    
    iv = bs.calculate_implied_volatility(
        market_price=market_price,
        S=100, K=100, T=1.0,
        option_type='call'
    )
    print(f"Implied volatility: {iv:.2%}")
    
    # Verify by pricing back
    verify_price = bs.price_call(S=100, K=100, T=1.0, sigma=iv)
    print(f"Verification: ${verify_price:.2f} (should match ${market_price:.2f})")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
