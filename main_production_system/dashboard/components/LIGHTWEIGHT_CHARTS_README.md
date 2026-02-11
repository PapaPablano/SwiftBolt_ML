# TradingView Lightweight Charts Integration

## Overview

Professional trading charts powered by TradingView's Lightweight Charts library.

## Features

- ✅ Candlestick OHLCV charts
- ✅ Multiple technical indicators (SMA, EMA, BB, RSI, MACD)
- ✅ Real-time updates
- ✅ Smooth performance (500+ candles)
- ✅ Drawing tools
- ✅ Responsive design

## Usage

```python
from components.lightweight_charts_wrapper import render_lightweight_chart

# Basic chart
render_lightweight_chart(df_raw, symbol='AAPL')

# With indicators
render_lightweight_chart(
    df_ohlcv=df_raw,
    symbol='AAPL',
    timeframe='1d',
    indicators=[
        {'type': 'sma', 'period': 20, 'color': 'orange'},
        {'type': 'sma', 'period': 50, 'color': 'blue'},
        {'type': 'bb', 'period': 20},
        {'type': 'rsi', 'period': 14},
    ],
)
```

## Supported Indicators

- `sma` - Simple Moving Average
- `ema` - Exponential Moving Average
- `bb` - Bollinger Bands
- `rsi` - Relative Strength Index
- `macd` - MACD

## Troubleshooting

If chart doesn't render:

1. Verify `df_ohlcv` has columns: time, open, high, low, close, volume
2. Check all values are numeric
3. Ensure dates are valid timestamps
4. Check that lightweight-charts is installed: `pip install lightweight-charts streamlit-lightweight-charts-pro`

## References

- Lightweight Charts Docs: https://github.com/louisnw01/lightweight-charts-python
- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/
- Streamlit Component: https://github.com/freyastreamlit/streamlit-lightweight-charts

