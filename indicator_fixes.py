#!/usr/bin/env python3
"""
Recommended fixes for SwiftBolt ML indicators
"""

# FIX 1: Increase data fetching
# Change your data fetching code from:
# bars = api.get_bars(symbol, timeframe, limit=10)
# To:
bars = api.get_bars(symbol, timeframe, limit=250)

# Or better, fetch by date range:
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=365)
bars = api.get_bars(symbol, timeframe, start=start.isoformat())


# FIX 3: Add validation for TA-Lib indicators
# Wrap each TA-Lib call with error handling:

def safe_talib_indicator(func, *args, **kwargs):
    '''Safely call TA-Lib function with error handling'''
    try:
        result = func(*args, **kwargs)
        if result is None or (isinstance(result, np.ndarray) and len(result) == 0):
            return np.nan
        return result
    except Exception as e:
        logger.warning(f"TA-Lib calculation failed: {e}")
        return np.nan

# Example usage:
df['williams_r'] = safe_talib_indicator(
    talib.WILLR, 
    df['high'], df['low'], df['close'], 
    timeperiod=14
)

df['cci'] = safe_talib_indicator(
    talib.CCI,
    df['high'], df['low'], df['close'],
    timeperiod=20
)


# FIX 4: Fix Market Correlation Features
# Add SPY data fetching:

# Fetch SPY data alongside your symbol
spy_bars = api.get_bars("SPY", timeframe, limit=250)
spy_df = pd.DataFrame({
    'timestamp': [b.t for b in spy_bars],
    'close': [b.c for b in spy_bars]
})

# Merge with main dataframe
df = df.merge(spy_df, on='timestamp', how='left', suffixes=('', '_spy'))

# Calculate correlations properly
df['spy_correlation_20d'] = df['close'].rolling(20).corr(df['close_spy'])
df['spy_correlation_60d'] = df['close'].rolling(60).corr(df['close_spy'])

# Calculate beta
df['returns_spy'] = df['close_spy'].pct_change()
cov = df['returns_1d'].rolling(20).cov(df['returns_spy'])
var = df['returns_spy'].rolling(20).var()
df['market_beta_20d'] = cov / var
