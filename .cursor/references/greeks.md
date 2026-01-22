# Options Greeks Reference

Complete mathematical definitions and practical interpretations of option Greeks for risk management and position analysis.

## The Greeks Overview

Greeks are mathematical derivatives that measure different dimensions of options risk. They quantify how an option's value changes in response to various market factors.

**Primary Greeks:**
- **Delta (Δ)**: Sensitivity to price changes in the underlying
- **Gamma (Γ)**: Rate of change of delta
- **Theta (Θ)**: Time decay of option value
- **Vega (ν)**: Sensitivity to volatility changes
- **Rho (ρ)**: Sensitivity to interest rate changes

## Delta (Δ)

### Definition
Delta measures the rate of change of the option value with respect to changes in the underlying asset's price.

**Mathematical Formula:**
```
Δ = ∂V / ∂S

For Call: Δ_call = N(d₁)
For Put: Δ_put = N(d₁) - 1 = -N(-d₁)

where:
d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
N(x) = cumulative standard normal distribution
S = current stock price
K = strike price
r = risk-free rate
σ = volatility
T = time to expiration
```

### Interpretation

**Range:**
- Call options: 0 to +1.0 (or 0 to +100 in percentage terms)
- Put options: -1.0 to 0 (or -100 to 0 in percentage terms)

**Meaning:**
- Delta of 0.50 means: for every $1 move in the underlying, the option moves approximately $0.50
- Delta of -0.30 means: for every $1 up in the underlying, the option loses approximately $0.30

**Moneyness Approximations:**
- Deep ITM Call: Δ ≈ +1.0 (moves almost 1:1 with stock)
- ATM Call: Δ ≈ +0.50 (50% correlation)
- Deep OTM Call: Δ ≈ 0 (almost no movement)
- Deep ITM Put: Δ ≈ -1.0
- ATM Put: Δ ≈ -0.50
- Deep OTM Put: Δ ≈ 0

### Practical Applications

**Portfolio Delta:**
```
Portfolio Δ = Σ (Δᵢ × Qtyᵢ × Multiplier)

For 100 shares of stock + 2 call contracts (Δ=0.40):
Portfolio Δ = 100 + (2 × 0.40 × 100) = 100 + 80 = 180
```

**Delta Hedging:**
To neutralize directional exposure, take opposite delta position:
```
Hedge Shares = -(Option Δ × Contracts × 100)

If short 5 calls with Δ=0.60:
Hedge Shares = -(0.60 × 5 × 100) = -300 shares
Buy 300 shares to hedge
```

**Probability Approximation:**
Delta roughly approximates the probability of the option expiring ITM:
- Delta of 0.70 ≈ 70% chance of expiring ITM
- Delta of 0.20 ≈ 20% chance of expiring ITM

### Python Implementation

```python
import numpy as np
from scipy.stats import norm

def calculate_delta_call(S, K, T, r, sigma):
    """Calculate delta for call option."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    return norm.cdf(d1)

def calculate_delta_put(S, K, T, r, sigma):
    """Calculate delta for put option."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    return norm.cdf(d1) - 1
```

## Gamma (Γ)

### Definition
Gamma measures the rate of change of delta with respect to changes in the underlying price. It's the second derivative of the option value.

**Mathematical Formula:**
```
Γ = ∂²V / ∂S² = ∂Δ / ∂S

For both calls and puts:
Γ = N'(d₁) / (S × σ × √T)

where:
N'(x) = (1/√(2π)) × e^(-x²/2)  [standard normal PDF]
```

### Interpretation

**Range:**
- Always positive for long options (both calls and puts)
- Always negative for short options

**Meaning:**
- Gamma of 0.05 means: for every $1 move in the underlying, delta changes by 0.05
- High gamma = delta changes rapidly (good for long options, risky for short)
- Low gamma = delta changes slowly (stable hedge ratios)

**Moneyness Behavior:**
- ATM options: Highest gamma
- ITM/OTM options: Lower gamma
- Gamma increases as expiration approaches for ATM options

### Practical Applications

**Delta Acceleration:**
```
New Δ ≈ Old Δ + (Γ × Stock Price Change)

If Δ=0.50, Γ=0.05, stock moves +$1:
New Δ ≈ 0.50 + (0.05 × 1) = 0.55
```

**Gamma Scalping:**
- Long gamma position: Buy stock when it falls, sell when it rises (profit from volatility)
- Short gamma position: Sell stock when it falls, buy when it rises (loses from volatility)

**Risk Management:**
High gamma positions require frequent delta hedging:
```
Hedge Frequency ∝ Γ × Volatility

High Γ, High σ → Hedge frequently
Low Γ, Low σ → Hedge infrequently
```

### Python Implementation

```python
def calculate_gamma(S, K, T, r, sigma):
    """Calculate gamma (same for calls and puts)."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))
```

## Theta (Θ)

### Definition
Theta measures the rate of change of the option value with respect to the passage of time (time decay).

**Mathematical Formula:**
```
Θ = -∂V / ∂T

For Call:
Θ_call = -[S×N'(d₁)×σ / (2×√T)] - r×K×e^(-rT)×N(d₂)

For Put:
Θ_put = -[S×N'(d₁)×σ / (2×√T)] + r×K×e^(-rT)×N(-d₂)

where:
d₂ = d₁ - σ√T
```

### Interpretation

**Range:**
- Typically negative for long options (value decays over time)
- Typically positive for short options (benefit from time decay)

**Meaning:**
- Theta of -$0.05 means: option loses approximately $0.05 per day
- Usually expressed as daily decay (divide annual theta by 365)

**Time Decay Characteristics:**
- Non-linear: accelerates as expiration approaches
- ATM options have highest theta
- Time decay fastest in final 30 days

### Practical Applications

**Time Decay Curve:**
```
Percentage of time value remaining:
90 DTE: ~70% remains
60 DTE: ~55% remains
30 DTE: ~35% remains
10 DTE: ~15% remains
1 DTE: ~3% remains
```

**Strategy Selection:**
- Theta positive strategies: Iron butterfly, iron condor, credit spreads
- Theta negative strategies: Long straddle, long strangle, debit spreads
- Calendar spreads: Exploit theta differential between expirations

**Daily P/L from Theta:**
```
Daily Theta P/L = Θ × Number of Contracts × 100

Portfolio with 10 short puts (Θ=+$0.08 each):
Daily Theta P/L = 0.08 × 10 × 100 = +$80 per day
```

### Python Implementation

```python
def calculate_theta_call(S, K, T, r, sigma):
    """Calculate theta for call option (annualized)."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)

    term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    term2 = -r * K * np.exp(-r*T) * norm.cdf(d2)

    return (term1 + term2) / 365  # Convert to daily

def calculate_theta_put(S, K, T, r, sigma):
    """Calculate theta for put option (annualized)."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)

    term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    term2 = r * K * np.exp(-r*T) * norm.cdf(-d2)

    return (term1 + term2) / 365  # Convert to daily
```

## Vega (ν)

### Definition
Vega measures the sensitivity of the option value to changes in implied volatility.

**Mathematical Formula:**
```
ν = ∂V / ∂σ

For both calls and puts:
ν = S × √T × N'(d₁)

where:
N'(d₁) = (1/√(2π)) × e^(-d₁²/2)
```

### Interpretation

**Range:**
- Always positive for long options
- Always negative for short options

**Meaning:**
- Vega of 0.15 means: for every 1% increase in IV, option value increases by $0.15
- Vega is highest for ATM options
- Longer-dated options have higher vega

**Volatility Impact:**
```
Option Value Change ≈ ν × IV Change

If ν=0.20 and IV increases from 25% to 30% (5% increase):
Value Change ≈ 0.20 × 5 = $1.00 increase
```

### Practical Applications

**Volatility Trading:**
- Long vega: Profit from IV expansion (long straddles, long options)
- Short vega: Profit from IV contraction (iron butterflies, short strangles)

**IV Rank Analysis:**
```
IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV)

High IV Rank (>70%): Consider short vega strategies
Low IV Rank (<30%): Consider long vega strategies
```

**Vega Exposure by Strategy:**
```
Long Straddle: High positive vega
Iron Butterfly: Negative vega
Calendar Spread: Positive vega (long dated > short dated)
Vertical Spread: Low vega (legs offset)
```

### Python Implementation

```python
def calculate_vega(S, K, T, r, sigma):
    """Calculate vega (same for calls and puts)."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    return S * np.sqrt(T) * norm.pdf(d1) / 100  # Divide by 100 for 1% change
```

## Rho (ρ)

### Definition
Rho measures the sensitivity of the option value to changes in the risk-free interest rate.

**Mathematical Formula:**
```
ρ = ∂V / ∂r

For Call:
ρ_call = K × T × e^(-rT) × N(d₂)

For Put:
ρ_put = -K × T × e^(-rT) × N(-d₂)
```

### Interpretation

**Range:**
- Calls: Positive rho
- Puts: Negative rho

**Meaning:**
- Rho of 0.05 means: for every 1% increase in interest rates, option value increases by $0.05
- Generally the least significant Greek for short-dated options
- More important for LEAPS (long-term options)

**Practical Impact:**
```
Typical rho for 30-day ATM option: ~0.02
Typical rho for 2-year LEAPS: ~0.50

Interest rate impact is minimal for most retail options trading
```

### Python Implementation

```python
def calculate_rho_call(S, K, T, r, sigma):
    """Calculate rho for call option."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return K * T * np.exp(-r*T) * norm.cdf(d2) / 100

def calculate_rho_put(S, K, T, r, sigma):
    """Calculate rho for put option."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return -K * T * np.exp(-r*T) * norm.cdf(-d2) / 100
```

## Multi-Leg Strategy Greeks

### Strategy Greek Calculation

**Portfolio Greeks:**
```
Total Δ = Σ (Δᵢ × Qtyᵢ × Multiplier × Sign)
Total Γ = Σ (Γᵢ × Qtyᵢ × Multiplier × Sign)
Total Θ = Σ (Θᵢ × Qtyᵢ × Multiplier × Sign)
Total ν = Σ (νᵢ × Qtyᵢ × Multiplier × Sign)

where Sign = +1 for long, -1 for short
```

**Example: Iron Butterfly**
```
Underlying: $100
Structure:
- Buy 1 Put @ $95 (Δ=-0.20, Γ=0.02, Θ=-$0.03, ν=0.08)
- Sell 1 Put @ $100 (Δ=-0.50, Γ=0.05, Θ=-$0.10, ν=0.15)
- Sell 1 Call @ $100 (Δ=+0.50, Γ=0.05, Θ=-$0.10, ν=0.15)
- Buy 1 Call @ $105 (Δ=+0.20, Γ=0.02, Θ=-$0.03, ν=0.08)

Portfolio Greeks:
Δ = [(-0.20×1×-1) + (-0.50×1×+1) + (0.50×1×+1) + (0.20×1×-1)] × 100
  = [0.20 - 0.50 + 0.50 - 0.20] × 100 = 0 (delta neutral)

Γ = [(0.02×-1) + (0.05×+1) + (0.05×+1) + (0.02×-1)] × 100
  = [-0.02 + 0.05 + 0.05 - 0.02] × 100 = 6 (short gamma)

Θ = [(−0.03×-1) + (−0.10×+1) + (−0.10×+1) + (−0.03×-1)] × 100
  = [0.03 - 0.10 - 0.10 + 0.03] × 100 = -$14/day (short theta)

ν = [(0.08×-1) + (0.15×+1) + (0.15×+1) + (0.08×-1)] × 100
  = [-0.08 + 0.15 + 0.15 - 0.08] × 100 = 14 (short vega)
```

## Greeks Interaction Matrix

| Greek | Increases When | Decreases When | Strategy Impact |
|-------|---------------|----------------|-----------------|
| Delta | Stock rises (calls), Stock falls (puts) | Stock falls (calls), Stock rises (puts) | Directional exposure |
| Gamma | Move to ATM, Time to expiration ↓ | Move to ITM/OTM, Time ↑ | Delta sensitivity |
| Theta | Move to ATM, Time to expiration ↓ | Move to ITM/OTM, Time ↑ | Time decay rate |
| Vega | Time to expiration ↑, Move to ATM | Time to expiration ↓, Move to ITM/OTM | IV sensitivity |
| Rho | Time to expiration ↑, Move to ITM | Time to expiration ↓, Move to OTM | Interest rate risk |

## Greek Risk Management Guidelines

**Delta Management:**
- Target: ±10% of portfolio value for directional bias
- Neutral: ±5% for market-neutral strategies
- Hedge when delta exceeds thresholds

**Gamma Management:**
- High gamma (short): Hedge frequently, tight stops
- Low gamma (long): Less frequent hedging
- Monitor gamma risk near expiration

**Theta Management:**
- Positive theta: Time is ally, avoid early exits
- Negative theta: Need significant moves, monitor decay
- Target theta/vega ratio for optimal risk/reward

**Vega Management:**
- Long vega: Profit from IV expansion, enter at low IV rank
- Short vega: Profit from IV contraction, enter at high IV rank
- Monitor VIX and IV percentile

## Complete Greeks Calculator

```python
class OptionGreeks:
    """Complete options Greeks calculator."""

    def __init__(self, S, K, T, r, sigma, option_type='call'):
        self.S = S  # Spot price
        self.K = K  # Strike price
        self.T = T  # Time to expiration (years)
        self.r = r  # Risk-free rate
        self.sigma = sigma  # Volatility
        self.option_type = option_type.lower()

        # Calculate d1 and d2
        self.d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
        self.d2 = self.d1 - sigma*np.sqrt(T)

    def delta(self):
        """Calculate delta."""
        if self.option_type == 'call':
            return norm.cdf(self.d1)
        else:
            return norm.cdf(self.d1) - 1

    def gamma(self):
        """Calculate gamma."""
        return norm.pdf(self.d1) / (self.S * self.sigma * np.sqrt(self.T))

    def theta(self):
        """Calculate theta (daily)."""
        term1 = -(self.S * norm.pdf(self.d1) * self.sigma) / (2 * np.sqrt(self.T))

        if self.option_type == 'call':
            term2 = -self.r * self.K * np.exp(-self.r*self.T) * norm.cdf(self.d2)
        else:
            term2 = self.r * self.K * np.exp(-self.r*self.T) * norm.cdf(-self.d2)

        return (term1 + term2) / 365

    def vega(self):
        """Calculate vega."""
        return self.S * np.sqrt(self.T) * norm.pdf(self.d1) / 100

    def rho(self):
        """Calculate rho."""
        if self.option_type == 'call':
            return self.K * self.T * np.exp(-self.r*self.T) * norm.cdf(self.d2) / 100
        else:
            return -self.K * self.T * np.exp(-self.r*self.T) * norm.cdf(-self.d2) / 100

    def all_greeks(self):
        """Return all Greeks as dictionary."""
        return {
            'delta': self.delta(),
            'gamma': self.gamma(),
            'theta': self.theta(),
            'vega': self.vega(),
            'rho': self.rho()
        }

# Usage example
option = OptionGreeks(S=100, K=100, T=30/365, r=0.04, sigma=0.25, option_type='call')
greeks = option.all_greeks()
print(f"Delta: {greeks['delta']:.4f}")
print(f"Gamma: {greeks['gamma']:.4f}")
print(f"Theta: {greeks['theta']:.4f}")
print(f"Vega: {greeks['vega']:.4f}")
print(f"Rho: {greeks['rho']:.4f}")
```

---

**References:**
- Hull, J. "Options, Futures, and Other Derivatives"
- Natenberg, S. "Option Volatility and Pricing"
- Black, F. and Scholes, M. "The Pricing of Options and Corporate Liabilities"
