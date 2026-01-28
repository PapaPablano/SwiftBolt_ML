# Polynomial S/R Quick Start Guide

## 🚀 30-Second Setup

```bash
# Install dependencies
cd SwiftBolt_ML/ml
pip install -r requirements_visualization.txt

# Run demo
python examples/polynomial_sr_example.py

# Output: polynomial_sr_chart.png
```

---

## 📊 Quick Examples

### 1. Basic Static Chart

```python
from src.features.sr_polynomial_fixed import SRPolynomialRegressor
from src.visualization.polynomial_sr_chart import create_flux_chart

# Your OHLC data
df = get_ohlc_data('AAPL')
pivots = detect_pivots(df)

# Fit & visualize
regressor = SRPolynomialRegressor(degree=2)
regressor.fit_support_curve(pivots)
regressor.fit_resistance_curve(pivots)

fig = create_flux_chart(
    df, regressor, pivots,
    style='dark',
    save_path='chart.png'
)
```

### 2. Interactive HTML Chart

```python
fig = create_flux_chart(
    df, regressor, pivots,
    style='dark',
    interactive=True,
    save_path='chart.html'
)
```

### 3. Command Line

```bash
# Demo with synthetic data
python examples/polynomial_sr_example.py

# Real symbol
python examples/polynomial_sr_example.py --symbol AAPL --days 60

# Interactive chart
python examples/polynomial_sr_example.py --interactive -o chart.html

# Cubic polynomial
python examples/polynomial_sr_example.py --degree 3 --forecast 100
```

---

## 🎨 Styling Options

### Dark Theme (TradingView Style)
```python
fig = create_flux_chart(df, regressor, pivots, style='dark')
```

### Light Theme
```python
fig = create_flux_chart(df, regressor, pivots, style='light')
```

### Custom Colors
```python
from src.visualization.polynomial_sr_chart import FluxChartVisualizer

viz = FluxChartVisualizer(style='dark')
viz.colors['support'] = '#00FF00'  # Green support
viz.colors['resistance'] = '#FF00FF'  # Magenta resistance

fig = viz.plot_polynomial_sr(df, regressor, pivots)
```

---

## 🔧 Common Configurations

### Conservative (Fewer Pivots)
```python
pivots = detect_pivots(df, left_bars=10, right_bars=10)
regressor = SRPolynomialRegressor(degree=1, min_points=6)
```

### Aggressive (More Pivots)
```python
pivots = detect_pivots(df, left_bars=3, right_bars=3)
regressor = SRPolynomialRegressor(degree=2, min_points=4)
```

### Smooth Curves (Cubic)
```python
regressor = SRPolynomialRegressor(degree=3, min_points=5)
```

### Simple Trend (Linear)
```python
regressor = SRPolynomialRegressor(degree=1, min_points=4)
```

---

## 📈 Feature Extraction for ML

```python
# Get current S/R levels
current_idx = len(df) - 1

support_level = regressor.predict_level(
    regressor.support_coeffs, current_idx, curve_type='support'
)

resistance_level = regressor.predict_level(
    regressor.resistance_coeffs, current_idx, curve_type='resistance'
)

# Get trend slopes (price/bar)
support_slope = regressor.compute_slope(
    regressor.support_coeffs, at_x=1.0, curve_type='support'
)

resistance_slope = regressor.compute_slope(
    regressor.resistance_coeffs, at_x=1.0, curve_type='resistance'
)

# Distance features
current_price = df.iloc[-1]['close']
dist_to_support = current_price - support_level
dist_to_resistance = resistance_level - current_price

# Add to DataFrame
df['poly_support'] = support_level
df['poly_resistance'] = resistance_level
df['support_slope'] = support_slope
df['resistance_slope'] = resistance_slope
df['dist_support_pct'] = dist_to_support / current_price
df['dist_resistance_pct'] = dist_to_resistance / current_price
```

---

## 🎯 Interpretation

### Support Slope
- **Positive (> 0.1)**: Rising support → Bullish trend
- **Negative (< -0.1)**: Falling support → Bearish trend
- **Flat (-0.1 to 0.1)**: Sideways/consolidation

### Resistance Slope
- **Positive (> 0.1)**: Rising resistance → Uptrend continuation
- **Negative (< -0.1)**: Falling resistance → Downtrend or compression
- **Flat (-0.1 to 0.1)**: Range-bound

### Distance Signals
- **Near support** (< 1%): Potential bounce or break
- **Near resistance** (< 1%): Potential rejection or breakout
- **Mid-channel**: Trend following opportunity

---

## ⚠️ Critical: Use Fixed Version

**❌ DON'T USE:**
```python
from src.features.sr_polynomial import SRPolynomialRegressor  # OLD
```

**✅ USE:**
```python
from src.features.sr_polynomial_fixed import SRPolynomialRegressor  # FIXED
```

**Why?** The fixed version has:
- ✅ Separate normalization for support/resistance
- ✅ Curve-type-aware predictions
- ✅ Properly scaled slopes

---

## 🐛 Troubleshooting

### "Not enough pivots"
```bash
# Increase data or reduce pivot bars
python examples/polynomial_sr_example.py --days 90 --pivot-bars 3
```

### "ModuleNotFoundError: plotly"
```bash
pip install plotly kaleido
```

### "Slopes seem wrong"
- Make sure you're using `sr_polynomial_fixed.py`
- Verify `curve_type` parameter in `predict_level()` and `compute_slope()`

### "Chart looks different than TradingView"
- Check pivot detection parameters match
- Verify polynomial degree is the same
- Ensure using same OHLC data timeframe

---

## 📚 Full Documentation

See [POLYNOMIAL_SR_VISUALIZATION.md](./POLYNOMIAL_SR_VISUALIZATION.md) for:
- Complete architecture details
- Data translation fixes explained
- Advanced customization
- Integration with ML pipeline
- Unit tests and validation

---

## 🔗 Key Files

| File | Purpose |
|------|----------|
| `src/features/sr_polynomial_fixed.py` | **Fixed regressor** (use this!) |
| `src/visualization/polynomial_sr_chart.py` | Chart generation |
| `examples/polynomial_sr_example.py` | Complete demo script |
| `docs/POLYNOMIAL_SR_VISUALIZATION.md` | Full documentation |
| `requirements_visualization.txt` | Dependencies |

---

## 💡 Pro Tips

1. **Always validate** pivots visually before trusting results
2. **Start with degree=2** (quadratic) for most use cases
3. **Use interactive charts** for exploration, static for reports
4. **Cache fitted curves** if analyzing multiple timeframes
5. **Combine with volume** for stronger signals
6. **Test different pivot sensitivities** for your asset class

---

## 🚦 Next Steps

1. Run the demo: `python examples/polynomial_sr_example.py`
2. Try with real  `--symbol AAPL --days 30`
3. Integrate into your ML pipeline
4. Create custom visualizations
5. Build trading signals on top

**Happy coding! 📊🚀**
