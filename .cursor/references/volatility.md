# Volatility Analysis Reference

Comprehensive guide to understanding, measuring, and forecasting volatility for options trading strategies.

## Volatility Fundamentals

### Historical Volatility (HV)

**Definition:** Actual price movement of the underlying asset over a specific period, measured as the annualized standard deviation of returns.

**Calculation:**
```python
import numpy as np
import pandas as pd

def calculate_historical_volatility(prices, window=20):
    """
    Calculate historical volatility from price series.

    Args:
        prices: pandas Series of closing prices
        window: number of periods (typically 20 for 20-day HV)

    Returns:
        Annualized volatility as percentage
    """
    # Calculate log returns
    log_returns = np.log(prices / prices.shift(1))

    # Calculate standard deviation
    volatility = log_returns.rolling(window=window).std()

    # Annualize (assuming 252 trading days)
    annualized_vol = volatility * np.sqrt(252) * 100

    return annualized_vol

# Example usage
# SPY prices for last 30 days
# hv_20 = calculate_historical_volatility(spy_prices, window=20)
```

**Common Windows:**
- 10-day HV: Very short-term, reactive to recent moves
- 20-day HV: Standard measure, ~1 month of trading
- 30-day HV: Aligns with typical option expiration cycle
- 60-day HV: Medium-term trend
- 252-day HV: Annual volatility estimate

**Interpretation:**
- **Low HV (<15%):** Market is calm, small daily movements
- **Normal HV (15-25%):** Typical range for major indices
- **Elevated HV (25-35%):** Increased uncertainty, larger moves
- **High HV (>35%):** Crisis, panic, or major news events

---

### Implied Volatility (IV)

**Definition:** Forward-looking expectation of volatility derived from option prices using pricing models (typically Black-Scholes).

**Key Concepts:**

1. **IV is not a prediction:** It represents what volatility must be for the current option price to be "fair" under the pricing model

2. **Mean Reversion:** IV tends to revert to long-term average levels

3. **Volatility Skew:** IV varies by strike price (typically higher for OTM puts)

4. **Term Structure:** IV varies by expiration date

**Calculation from Option Prices:**
```python
from scipy.optimize import brentq
from scipy.stats import norm
import numpy as np

def black_scholes_call(S, K, T, r, sigma):
    """Calculate BS call price."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)

def black_scholes_put(S, K, T, r, sigma):
    """Calculate BS put price."""
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

def implied_volatility(option_price, S, K, T, r, option_type='call'):
    """
    Calculate implied volatility from market price.

    Args:
        option_price: Market price of the option
        S: Current stock price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        option_type: 'call' or 'put'

    Returns:
        Implied volatility as decimal (e.g., 0.25 for 25%)
    """
    def objective(sigma):
        if option_type == 'call':
            return black_scholes_call(S, K, T, r, sigma) - option_price
        else:
            return black_scholes_put(S, K, T, r, sigma) - option_price

    try:
        iv = brentq(objective, 0.001, 5.0)  # Search between 0.1% and 500%
        return iv
    except:
        return np.nan

# Example usage
# S = 450, K = 450, T = 30/365, r = 0.05, call_price = 8.50
# iv = implied_volatility(8.50, 450, 450, 30/365, 0.05, 'call')
# print(f"Implied Volatility: {iv*100:.2f}%")
```

---

### IV Rank and IV Percentile

**IV Rank:**
```
IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) × 100
```

**Interpretation:**
- **0-20:** IV is historically low (consider buying options)
- **20-40:** Below average volatility
- **40-60:** Middle range
- **60-80:** Above average volatility
- **80-100:** IV is historically high (consider selling options)

**IV Percentile:**
Percentage of days in the past year where IV was lower than current IV.

**Calculation:**
```python
def calculate_iv_rank(current_iv, iv_series):
    """
    Calculate IV Rank from historical IV data.

    Args:
        current_iv: Current implied volatility (%)
        iv_series: pandas Series of historical IV values

    Returns:
        IV Rank (0-100)
    """
    iv_min = iv_series.min()
    iv_max = iv_series.max()

    if iv_max == iv_min:
        return 50.0

    iv_rank = (current_iv - iv_min) / (iv_max - iv_min) * 100
    return iv_rank

def calculate_iv_percentile(current_iv, iv_series):
    """
    Calculate IV Percentile from historical IV data.

    Args:
        current_iv: Current implied volatility (%)
        iv_series: pandas Series of historical IV values

    Returns:
        IV Percentile (0-100)
    """
    days_below = (iv_series < current_iv).sum()
    total_days = len(iv_series)

    iv_percentile = (days_below / total_days) * 100
    return iv_percentile

# Example
# current_iv = 25.0
# historical_ivs = pd.Series([18, 22, 24, 26, 30, 28, 23, ...])
# rank = calculate_iv_rank(current_iv, historical_ivs)
# percentile = calculate_iv_percentile(current_iv, historical_ivs)
```

---

## Volatility Term Structure

**Definition:** Relationship between implied volatility and time to expiration.

**Normal Term Structure:**
- Near-term options: Lower IV (less uncertainty over short period)
- Long-term options: Higher IV (more uncertainty over longer period)
- Upward sloping curve

**Inverted Term Structure:**
- Near-term IV > Long-term IV
- Indicates near-term event (earnings, FDA decision, etc.)
- Creates calendar spread opportunities

**Flat Term Structure:**
- Similar IV across expirations
- Market uncertainty extends across time periods

**Calculation:**
```python
def analyze_term_structure(options_chain):
    """
    Analyze IV term structure across expirations.

    Args:
        options_chain: dict with expirations as keys, IV data as values

    Returns:
        DataFrame with term structure analysis
    """
    import pandas as pd

    term_structure = []

    for expiration, chain_data in sorted(options_chain.items()):
        # Get ATM options for consistent comparison
        atm_iv = chain_data['atm_iv']
        days_to_exp = chain_data['days_to_expiration']

        term_structure.append({
            'expiration': expiration,
            'days': days_to_exp,
            'atm_iv': atm_iv
        })

    df = pd.DataFrame(term_structure)

    # Calculate slope
    if len(df) >= 2:
        slope = (df.iloc[-1]['atm_iv'] - df.iloc[0]['atm_iv']) / \
                (df.iloc[-1]['days'] - df.iloc[0]['days'])

        structure_type = 'UPWARD' if slope > 0.01 else \
                        'INVERTED' if slope < -0.01 else 'FLAT'
    else:
        structure_type = 'INSUFFICIENT_DATA'

    return df, structure_type
```

---

## Volatility Skew

**Definition:** IV varies by strike price, typically showing different values for OTM puts vs calls.

**Common Skew Patterns:**

1. **Equity Skew (Put Skew):**
   - OTM puts have higher IV than ATM or OTM calls
   - Market fears downside more than upside
   - "Volatility smile" shape

2. **Reverse Skew:**
   - OTM calls have higher IV (rare in equities)
   - Common in commodities or assets with supply constraints

3. **Flat Skew:**
   - Similar IV across strikes
   - Rare, indicates balanced supply/demand

**Measurement:**
```python
def calculate_skew(options_chain, spot_price):
    """
    Calculate volatility skew metrics.

    Args:
        options_chain: DataFrame with strikes and IVs
        spot_price: Current underlying price

    Returns:
        Skew metrics dictionary
    """
    # Separate calls and puts
    calls = options_chain[options_chain['type'] == 'call']
    puts = options_chain[options_chain['type'] == 'put']

    # Find ATM strike
    atm_strike = calls.iloc[(calls['strike'] - spot_price).abs().argsort()[:1]]['strike'].values[0]

    # Get ATM IV
    atm_iv = calls[calls['strike'] == atm_strike]['iv'].values[0]

    # Get 25-delta put IV (typically ~5-10% OTM)
    put_25delta = puts[puts['delta'].abs().between(0.20, 0.30)].iloc[0]

    # Get 25-delta call IV
    call_25delta = calls[calls['delta'].between(0.20, 0.30)].iloc[0]

    # Calculate skew
    put_skew = put_25delta['iv'] - atm_iv
    call_skew = call_25delta['iv'] - atm_iv
    butterfly_skew = ((put_25delta['iv'] + call_25delta['iv']) / 2) - atm_iv

    return {
        'atm_iv': atm_iv,
        'put_25d_iv': put_25delta['iv'],
        'call_25d_iv': call_25delta['iv'],
        'put_skew': put_skew,
        'call_skew': call_skew,
        'butterfly_skew': butterfly_skew,
        'skew_type': 'PUT_SKEW' if put_skew > call_skew else 'CALL_SKEW'
    }
```

---

## Expected Move Calculation

**Definition:** Expected price range based on implied volatility.

**Formula:**
```
Expected Move = Stock Price × IV × √(Days to Expiration / 365)
```

**Interpretation:**
- 68% probability (1 standard deviation): Price will be within ± Expected Move
- 95% probability (2 standard deviations): Price will be within ± 2 × Expected Move

**Implementation:**
```python
def calculate_expected_move(stock_price, iv, days_to_expiration):
    """
    Calculate expected move based on IV.

    Args:
        stock_price: Current stock price
        iv: Implied volatility (as decimal, e.g., 0.25 for 25%)
        days_to_expiration: Days until expiration

    Returns:
        Dictionary with expected moves
    """
    import math

    # Calculate 1 standard deviation move
    time_fraction = math.sqrt(days_to_expiration / 365)
    one_sd_move = stock_price * iv * time_fraction

    # Calculate ranges
    return {
        'current_price': stock_price,
        'iv_annual': iv * 100,
        'days': days_to_expiration,
        'one_sd_move': one_sd_move,
        'one_sd_range': (stock_price - one_sd_move, stock_price + one_sd_move),
        'one_sd_probability': 68.2,
        'two_sd_move': one_sd_move * 2,
        'two_sd_range': (stock_price - one_sd_move*2, stock_price + one_sd_move*2),
        'two_sd_probability': 95.4,
        'three_sd_move': one_sd_move * 3,
        'three_sd_range': (stock_price - one_sd_move*3, stock_price + one_sd_move*3),
        'three_sd_probability': 99.7
    }

# Example
# SPY @ $450, 30 days to expiration, IV = 20%
# move = calculate_expected_move(450, 0.20, 30)
# Output:
# {
#     'one_sd_move': 8.85,  # $450 ± $8.85
#     'one_sd_range': (441.15, 458.85),
#     'one_sd_probability': 68.2
# }
```

**Practical Application:**
```python
def analyze_straddle_breakevens(stock_price, iv, days_to_exp, total_premium):
    """
    Compare straddle breakevens with expected move.

    Returns assessment of whether breakevens are within expected range.
    """
    expected = calculate_expected_move(stock_price, iv, days_to_exp)

    # Straddle breakevens
    upper_breakeven = stock_price + total_premium
    lower_breakeven = stock_price - total_premium

    # Compare with 1 SD
    one_sd_upper = expected['one_sd_range'][1]
    one_sd_lower = expected['one_sd_range'][0]

    analysis = {
        'breakevens': (lower_breakeven, upper_breakeven),
        'expected_range_1sd': expected['one_sd_range'],
        'breakeven_width': total_premium * 2,
        'expected_move_1sd': expected['one_sd_move'] * 2,
        'premium_to_move_ratio': (total_premium * 2) / (expected['one_sd_move'] * 2)
    }

    # Assessment
    if total_premium < expected['one_sd_move']:
        analysis['assessment'] = 'FAVORABLE - Breakevens within 1 SD'
    elif total_premium < expected['two_sd_move']:
        analysis['assessment'] = 'MODERATE - Breakevens within 2 SD'
    else:
        analysis['assessment'] = 'UNFAVORABLE - Breakevens beyond 2 SD'

    return analysis
```

---

## Volatility Forecasting

### GARCH Model (Generalized Autoregressive Conditional Heteroskedasticity)

**Concept:** Volatility clusters - high volatility follows high volatility, low follows low.

**Simple Implementation:**
```python
from arch import arch_model

def forecast_volatility_garch(returns, horizon=30):
    """
    Forecast volatility using GARCH(1,1) model.

    Args:
        returns: pandas Series of daily returns
        horizon: forecast horizon in days

    Returns:
        Forecasted volatility (annualized %)
    """
    # Fit GARCH(1,1) model
    model = arch_model(returns*100, vol='Garch', p=1, q=1)
    fitted_model = model.fit(disp='off')

    # Forecast
    forecast = fitted_model.forecast(horizon=horizon)
    forecasted_var = forecast.variance.values[-1, :]

    # Convert to annualized volatility
    forecasted_vol = np.sqrt(forecasted_var.mean()) * np.sqrt(252) / 100

    return forecasted_vol
```

### Simple Moving Average Forecast

```python
def forecast_volatility_sma(historical_vol, window=20):
    """
    Simple moving average forecast.

    Args:
        historical_vol: pandas Series of historical volatility
        window: lookback window

    Returns:
        Forecasted volatility
    """
    return historical_vol.rolling(window=window).mean().iloc[-1]
```

### Exponential Weighted Moving Average (EWMA)

```python
def forecast_volatility_ewma(returns, lambda_param=0.94):
    """
    EWMA volatility forecast (RiskMetrics approach).

    Args:
        returns: pandas Series of daily returns
        lambda_param: decay factor (0.94 standard for daily data)

    Returns:
        Forecasted volatility (annualized %)
    """
    # Calculate squared returns
    squared_returns = returns**2

    # Apply EWMA
    ewma_var = squared_returns.ewm(alpha=1-lambda_param, adjust=False).mean()

    # Convert to annualized volatility
    forecasted_vol = np.sqrt(ewma_var.iloc[-1] * 252) * 100

    return forecasted_vol
```

---

## Volatility Event Analysis

### Earnings Volatility Pattern

**Typical Pattern:**
1. **Pre-earnings:** IV increases as event approaches (IV crush setup)
2. **Post-earnings:** IV drops sharply after announcement
3. **Recovery:** IV gradually returns to normal levels

**Analysis:**
```python
def analyze_earnings_iv_pattern(ticker, earnings_dates):
    """
    Analyze IV behavior around earnings dates.

    Returns average IV change pre/post earnings.
    """
    iv_changes = []

    for earnings_date in earnings_dates:
        # Get IV 7 days before
        pre_iv = get_iv_at_date(ticker, earnings_date - timedelta(days=7))

        # Get IV 1 day after
        post_iv = get_iv_at_date(ticker, earnings_date + timedelta(days=1))

        iv_change = (post_iv - pre_iv) / pre_iv * 100
        iv_changes.append(iv_change)

    return {
        'avg_iv_drop': np.mean(iv_changes),
        'median_iv_drop': np.median(iv_changes),
        'std_iv_drop': np.std(iv_changes),
        'max_iv_drop': min(iv_changes),
        'typical_pattern': 'IV CRUSH' if np.mean(iv_changes) < -10 else 'MODERATE'
    }
```

### VIX Correlation

**VIX (CBOE Volatility Index):**
- Measures S&P 500 implied volatility
- "Fear gauge" for market uncertainty

**Correlation Analysis:**
```python
def analyze_vix_correlation(ticker_ivs, vix_values):
    """
    Analyze correlation between ticker IV and VIX.

    High correlation means ticker moves with market volatility.
    """
    correlation = ticker_ivs.corr(vix_values)

    return {
        'correlation': correlation,
        'interpretation': 'HIGH MARKET BETA' if correlation > 0.7 else
                         'MODERATE MARKET BETA' if correlation > 0.4 else
                         'LOW MARKET BETA'
    }
```

---

## Volatility Trading Strategies by Regime

### High IV Environment (IV Rank > 70)

**Recommended Strategies:**
- **Iron Butterfly:** Sell volatility, collect premium
- **Iron Condor:** Wider range, sell high IV
- **Credit Spreads:** Benefit from IV crush

**Risk:** Market moves more than expected

### Low IV Environment (IV Rank < 30)

**Recommended Strategies:**
- **Long Straddle:** Buy cheap volatility
- **Long Strangle:** Lower cost volatility play
- **Debit Spreads:** Directional plays at low cost

**Risk:** Volatility doesn't expand

### Rising IV Environment

**Recommended Strategies:**
- **Calendar Spreads:** Sell near-term, buy longer-term
- **Diagonal Spreads:** Benefit from term structure steepening
- **Long options before events:** IV expansion play

### Falling IV Environment (Post-Event)

**Recommended Strategies:**
- **Close long volatility positions:** Lock in IV gains
- **Sell short-term options:** Capitalize on elevated levels
- **Avoid buying options:** IV decay hurts long positions

---

## Practical Volatility Checklist

**Before Opening Position:**
- [ ] Check IV Rank / IV Percentile (use 52-week lookback)
- [ ] Calculate expected move for expiration
- [ ] Compare breakevens with expected move
- [ ] Review term structure (normal, inverted, or flat)
- [ ] Check for upcoming events (earnings, FDA, economic data)
- [ ] Analyze historical volatility vs. implied volatility
- [ ] Assess skew pattern and positioning

**During Position Management:**
- [ ] Monitor IV changes daily
- [ ] Track Vega exposure ($ change per 1% IV move)
- [ ] Watch for term structure shifts
- [ ] Prepare for event-driven IV changes

**Post-Trade Analysis:**
- [ ] Compare actual volatility to implied
- [ ] Analyze IV realization vs. forecast
- [ ] Document whether IV expansion/contraction occurred
- [ ] Update forecasting models

---

## Reference Formulas

**Annualized Volatility from Daily Returns:**
```
σ_annual = σ_daily × √252
```

**Expected Move (1 SD):**
```
EM = S × σ × √(t / 365)
where S = stock price, σ = IV, t = days
```

**Probability of Profit (short option):**
```
PoP ≈ 100 - (|Delta| × 100)
For ATM option: ~50%
For 30-delta option: ~70%
```

**IV Rank:**
```
IV_Rank = (IV_current - IV_52w_low) / (IV_52w_high - IV_52w_low) × 100
```

---

*This reference is based on quantitative finance literature, CBOE methodologies, and Options Industry Council educational materials.*
