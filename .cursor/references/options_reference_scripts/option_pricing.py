"""
Options Pricing and Greeks Calculator

Black-Scholes model implementation for European options with full Greeks calculation.

Author: Ordinis-1 Project
License: Educational Use
"""

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass
class OptionParameters:
    """Parameters for option pricing."""

    S: float  # Current stock price
    K: float  # Strike price
    T: float  # Time to expiration (years)
    r: float  # Risk-free rate (annual)
    sigma: float  # Implied volatility (annual)
    option_type: str  # 'call' or 'put'


class BlackScholesCalculator:
    """Black-Scholes pricing model with Greeks calculation."""

    def __init__(self):
        """Initialize calculator."""

    @staticmethod
    def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 parameter."""
        if T <= 0 or sigma <= 0:
            raise ValueError("T and sigma must be positive")

        return (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def _d2(d1: float, sigma: float, T: float) -> float:
        """Calculate d2 parameter."""
        return d1 - sigma * np.sqrt(T)

    def call_price(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate European call option price using Black-Scholes.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate (annual, as decimal)
            sigma: Implied volatility (annual, as decimal)

        Returns:
            Call option price

        Example:
            >>> calc = BlackScholesCalculator()
            >>> price = calc.call_price(100, 100, 0.25, 0.05, 0.20)
            >>> print(f"Call price: ${price:.2f}")
        """
        if T <= 0:
            return max(S - K, 0)

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return call

    def put_price(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate European put option price using Black-Scholes.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate (annual, as decimal)
            sigma: Implied volatility (annual, as decimal)

        Returns:
            Put option price

        Example:
            >>> calc = BlackScholesCalculator()
            >>> price = calc.put_price(100, 100, 0.25, 0.05, 0.20)
            >>> print(f"Put price: ${price:.2f}")
        """
        if T <= 0:
            return max(K - S, 0)

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        put = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return put

    def delta_call(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate delta for call option.

        Delta measures the rate of change of option price with respect to
        changes in the underlying asset's price.

        Returns:
            Delta value (between 0 and 1 for calls)
        """
        if T <= 0:
            return 1.0 if S > K else 0.0

        d1 = self._d1(S, K, T, r, sigma)
        return norm.cdf(d1)

    def delta_put(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate delta for put option.

        Returns:
            Delta value (between -1 and 0 for puts)
        """
        if T <= 0:
            return -1.0 if S < K else 0.0

        d1 = self._d1(S, K, T, r, sigma)
        return norm.cdf(d1) - 1

    def gamma(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate gamma (same for calls and puts).

        Gamma measures the rate of change in delta with respect to changes
        in the underlying price.

        Returns:
            Gamma value (always positive)
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))

    def vega(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate vega (same for calls and puts).

        Vega measures sensitivity to a 1% change in implied volatility.

        Returns:
            Vega value per 1% IV change
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        return S * norm.pdf(d1) * np.sqrt(T) / 100

    def theta_call(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate theta for call option (daily).

        Theta measures the rate of time decay. Returns daily theta.

        Returns:
            Theta value per day (typically negative)
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)

        # Convert to daily theta
        return theta / 365

    def theta_put(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate theta for put option (daily).

        Returns:
            Theta value per day (typically negative)
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(
            -d2
        )

        # Convert to daily theta
        return theta / 365

    def rho_call(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate rho for call option.

        Rho measures sensitivity to a 1% change in interest rates.

        Returns:
            Rho value per 1% rate change
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        return K * T * np.exp(-r * T) * norm.cdf(d2) / 100

    def rho_put(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate rho for put option.

        Returns:
            Rho value per 1% rate change
        """
        if T <= 0:
            return 0.0

        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, sigma, T)

        return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100

    def all_greeks(self, params: OptionParameters) -> dict[str, float]:
        """
        Calculate all Greeks for an option.

        Args:
            params: OptionParameters dataclass with option details

        Returns:
            Dictionary with price and all Greeks

        Example:
            >>> calc = BlackScholesCalculator()
            >>> params = OptionParameters(
            ...     S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call'
            ... )
            >>> greeks = calc.all_greeks(params)
            >>> for key, value in greeks.items():
            ...     print(f"{key}: {value:.4f}")
        """
        S, K, T, r, sigma = params.S, params.K, params.T, params.r, params.sigma
        is_call = params.option_type.lower() == "call"

        result = {
            "price": self.call_price(S, K, T, r, sigma)
            if is_call
            else self.put_price(S, K, T, r, sigma),
            "delta": self.delta_call(S, K, T, r, sigma)
            if is_call
            else self.delta_put(S, K, T, r, sigma),
            "gamma": self.gamma(S, K, T, r, sigma),
            "vega": self.vega(S, K, T, r, sigma),
            "theta": self.theta_call(S, K, T, r, sigma)
            if is_call
            else self.theta_put(S, K, T, r, sigma),
            "rho": self.rho_call(S, K, T, r, sigma) if is_call else self.rho_put(S, K, T, r, sigma),
        }

        return result


def calculate_implied_volatility(
    option_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    max_iterations: int = 100,
    tolerance: float = 1e-5,
) -> float:
    """
    Calculate implied volatility using Newton-Raphson method.

    Args:
        option_price: Market price of the option
        S: Current stock price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        option_type: 'call' or 'put'
        max_iterations: Maximum iterations for convergence
        tolerance: Convergence tolerance

    Returns:
        Implied volatility as decimal (e.g., 0.25 for 25%)

    Raises:
        ValueError: If convergence fails

    Example:
        >>> iv = calculate_implied_volatility(
        ...     option_price=8.50, S=100, K=100, T=0.25, r=0.05, option_type='call'
        ... )
        >>> print(f"Implied Volatility: {iv*100:.2f}%")
    """
    calc = BlackScholesCalculator()

    # Initial guess
    sigma = 0.25

    for i in range(max_iterations):
        # Calculate option price and vega
        if option_type.lower() == "call":
            price = calc.call_price(S, K, T, r, sigma)
        else:
            price = calc.put_price(S, K, T, r, sigma)

        vega = calc.vega(S, K, T, r, sigma) * 100  # Convert back to per 100% change

        # Check convergence
        diff = price - option_price
        if abs(diff) < tolerance:
            return sigma

        # Newton-Raphson update
        if vega == 0:
            raise ValueError("Vega is zero, cannot calculate IV")

        sigma = sigma - diff / vega

        # Ensure sigma stays positive
        if sigma <= 0:
            sigma = 0.01

    raise ValueError(f"IV calculation did not converge after {max_iterations} iterations")


def calculate_expected_move(
    stock_price: float, iv: float, days_to_expiration: int
) -> dict[str, float]:
    """
    Calculate expected price move based on implied volatility.

    Args:
        stock_price: Current stock price
        iv: Implied volatility (as decimal, e.g., 0.25 for 25%)
        days_to_expiration: Days until expiration

    Returns:
        Dictionary with expected moves at 1, 2, and 3 standard deviations

    Example:
        >>> move = calculate_expected_move(450, 0.20, 30)
        >>> print(f"1 SD Move: ±${move['one_sd_move']:.2f}")
        >>> print(f"Range: ${move['one_sd_range'][0]:.2f} - ${move['one_sd_range'][1]:.2f}")
    """
    time_fraction = np.sqrt(days_to_expiration / 365)
    one_sd_move = stock_price * iv * time_fraction

    return {
        "current_price": stock_price,
        "iv_annual_pct": iv * 100,
        "days": days_to_expiration,
        "one_sd_move": one_sd_move,
        "one_sd_range": (stock_price - one_sd_move, stock_price + one_sd_move),
        "one_sd_probability": 68.2,
        "two_sd_move": one_sd_move * 2,
        "two_sd_range": (stock_price - one_sd_move * 2, stock_price + one_sd_move * 2),
        "two_sd_probability": 95.4,
        "three_sd_move": one_sd_move * 3,
        "three_sd_range": (stock_price - one_sd_move * 3, stock_price + one_sd_move * 3),
        "three_sd_probability": 99.7,
    }


if __name__ == "__main__":
    # Example usage
    print("=== Black-Scholes Options Calculator ===\n")

    # Example 1: ATM Call
    print("Example 1: ATM Call Option")
    params = OptionParameters(
        S=100.0,  # Stock at $100
        K=100.0,  # Strike at $100 (ATM)
        T=0.25,  # 3 months (0.25 years)
        r=0.05,  # 5% risk-free rate
        sigma=0.20,  # 20% implied volatility
        option_type="call",
    )

    calc = BlackScholesCalculator()
    greeks = calc.all_greeks(params)

    print(f"Stock Price: ${params.S:.2f}")
    print(f"Strike Price: ${params.K:.2f}")
    print(f"Time to Expiration: {params.T*365:.0f} days")
    print(f"Implied Volatility: {params.sigma*100:.1f}%")
    print(f"\nOption Price: ${greeks['price']:.2f}")
    print(f"Delta: {greeks['delta']:.4f}")
    print(f"Gamma: {greeks['gamma']:.4f}")
    print(f"Theta (daily): ${greeks['theta']:.4f}")
    print(f"Vega (per 1% IV): ${greeks['vega']:.4f}")
    print(f"Rho (per 1% rate): ${greeks['rho']:.4f}")

    # Example 2: Implied Volatility
    print("\n\nExample 2: Implied Volatility Calculation")
    market_price = 8.50
    iv = calculate_implied_volatility(
        option_price=market_price, S=100, K=100, T=0.25, r=0.05, option_type="call"
    )
    print(f"Market Price: ${market_price:.2f}")
    print(f"Implied Volatility: {iv*100:.2f}%")

    # Example 3: Expected Move
    print("\n\nExample 3: Expected Move for SPY")
    move = calculate_expected_move(stock_price=450.0, iv=0.18, days_to_expiration=30)
    print("Stock: $450.00")
    print(f"IV: {move['iv_annual_pct']:.1f}%")
    print(f"Days: {move['days']}")
    print(f"\n1 SD Move: ±${move['one_sd_move']:.2f}")
    print(f"  Range: ${move['one_sd_range'][0]:.2f} - ${move['one_sd_range'][1]:.2f}")
    print(f"  Probability: {move['one_sd_probability']:.1f}%")
    print(f"\n2 SD Move: ±${move['two_sd_move']:.2f}")
    print(f"  Range: ${move['two_sd_range'][0]:.2f} - ${move['two_sd_range'][1]:.2f}")
    print(f"  Probability: {move['two_sd_probability']:.1f}%")
