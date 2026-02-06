# Diversified Validation Guide

## Why Test Diverse Stocks?

**Problem:** A model that works on AAPL might fail on JNJ because it's overfit to tech stocks.

**Solution:** Test across sectors, volatility regimes, and market caps to ensure generalization.

## Your Diversified Test Set

### Stock Selection (Research-Backed)

| Symbol | Sector | Volatility | Type | Why Included |
|--------|--------|------------|------|-------------|
| **PG** | Consumer Staples | Low | Defensive | Stable, slow trends, dividend-focused |
| **KO** | Consumer Staples | Low | Defensive | Classic defensive stock, recession-resistant |
| **JNJ** | Healthcare | Low | Defensive | Healthcare stability, different from tech |
| **MSFT** | Technology | Medium | Mega-cap | Baseline mega-cap tech (you're testing anyway) |
| **AMGN** | Biotech | Medium | Growth | Event-driven (FDA approvals, trials) |
| **NVDA** | Technology | High | High Growth | Extreme momentum, tests volatility handling |
| **MU** | Semiconductors | High | Cyclical | Boom/bust cycles, chip sector |
| **ALB** | Materials/Lithium | Very High | Cyclical | Commodity exposure, EV demand cycles |

**Coverage:**
- ✅ 5 sectors (Staples, Healthcare, Tech, Biotech, Semi, Materials)
- ✅ 4 volatility levels (Low, Medium, High, Very High)
- ✅ 4 stock types (Defensive, Mega-cap, Growth, Cyclical)

**Research backing:** [web:107] [web:111]

---

## Quick Start (3 Steps)

### Step 1: Run Validation (2-3 hours)
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
chmod +x scripts/run_diversified_validation.sh
./scripts/run_diversified_validation.sh
```

**What this does:**
- Tests 8 stocks × 60 days × 4 horizons = ~1,920 predictions
- Trains on data before each test date (no look-ahead)
- Records predictions + actual outcomes

**Expected output:**
```
Validating PG
  PG walk-forward: 100%|████████| 60/60 [02:15<00:00, 0.44it/s]
  Total predictions: 240
  Accuracy: 58.3%
  
Validating KO
  ...
  
OVERALL ACCURACY: 61.2% (1920 predictions)
```

### Step 2: Analyze for Overfitting (1 minute)
```bash
python scripts/analyze_validation_diversity.py \
  validation_results/diversified/validation_results_*.csv
```

**What this checks:**
- Are accuracies similar across sectors? (No sector cherry-picking)
- Does model work in low AND high volatility? (No regime overfitting)
- Is variance across stocks acceptable? (< 15% std dev)

**Example output:**
```
Per-Sector Accuracy (Overfitting Check):
  Consumer Staples    :  62.5% (n= 480, symbols=2)
  Healthcare          :  59.3% (n= 240, symbols=1)
  Technology          :  63.1% (n= 480, symbols=2)
  Biotech             :  58.7% (n= 240, symbols=1)
  Semiconductors      :  60.2% (n= 240, symbols=1)
  Materials           :  57.9% (n= 240, symbols=1)
  
  ✓ Sector performance is consistent (range=5.2%)
  
Per-Volatility Accuracy (Regime Check):
  Low         :  61.1% (n= 720, symbols=3)
  Medium      :  60.8% (n= 480, symbols=2)
  High        :  59.5% (n= 480, symbols=2)
  Very High   :  57.9% (n= 240, symbols=1)
  
  ✓ Works across volatility regimes (range=3.2%)
  
Overfitting Risk Assessment:
  ✓ LOW RISK: Consistent performance across diverse stocks (std=2.1%)
     Action: Model generalizes well, safe to deploy
```

### Step 3: Decision

**Deploy if:**
- ✅ Overall accuracy > 55%
- ✅ Sector std dev < 15%
- ✅ No single sector/volatility dominates
- ✅ Range between best/worst < 25%

**Investigate if:**
- ⚠️ Accuracy 50-55% (marginal)
- ⚠️ One sector significantly better (overfitting)
- ⚠️ High volatility stocks fail (regime-specific)

**Do NOT deploy if:**
- 🛑 Accuracy < 50%
- 🛑 Std dev > 15% across stocks
- 🛑 >25% gap between best/worst

---

## Understanding Overfitting Patterns

### Pattern 1: Sector Overfitting
```
Technology:     75.2%  ← Much better
Healthcare:     52.1%  ← Much worse
Materials:      48.9%  ← Much worse
```
**Problem:** Model only works on tech stocks  
**Cause:** Training data dominated by tech, or features specific to tech  
**Action:** Retrain with balanced dataset, or deploy only for tech

### Pattern 2: Volatility Overfitting
```
Low volatility:   68.3%  ← Great!
High volatility:  43.2%  ← Fails!
```
**Problem:** Model can't handle wild swings  
**Cause:** Features/signals optimized for calm markets  
**Action:** Add volatility-adjusted features, or use only in calm markets

### Pattern 3: Good Generalization ✓
```
All sectors:      58-63%  ← Consistent
All volatilities: 57-62%  ← Consistent  
Std dev: 2.3%            ← Low variance
```
**Assessment:** Model generalizes well  
**Action:** Deploy with confidence!

---

## Advanced Analysis

### Load Results in Python
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load results
df = pd.read_csv('validation_results/diversified/validation_results_*.csv')

# Add categories
STOCK_CATEGORIES = {
    'PG': {'sector': 'Consumer Staples', 'volatility': 'Low'},
    'KO': {'sector': 'Consumer Staples', 'volatility': 'Low'},
    'JNJ': {'sector': 'Healthcare', 'volatility': 'Low'},
    'MSFT': {'sector': 'Technology', 'volatility': 'Medium'},
    'AMGN': {'sector': 'Biotech', 'volatility': 'Medium'},
    'NVDA': {'sector': 'Technology', 'volatility': 'High'},
    'MU': {'sector': 'Semiconductors', 'volatility': 'High'},
    'ALB': {'sector': 'Materials', 'volatility': 'Very High'},
}

df['sector'] = df['symbol'].map(lambda s: STOCK_CATEGORIES[s]['sector'])
df['volatility'] = df['symbol'].map(lambda s: STOCK_CATEGORIES[s]['volatility'])

# Heatmap: Sector × Horizon accuracy
pivot = df.groupby(['sector', 'horizon'])['correct'].mean().unstack()
sns.heatmap(pivot, annot=True, fmt='.1%', cmap='RdYlGn', center=0.5)
plt.title('Accuracy by Sector and Horizon')
plt.show()

# Check distribution shift over time
df['test_date'] = pd.to_datetime(df['test_date'])
df.groupby('test_date')['correct'].mean().plot()
plt.axhline(0.5, color='r', linestyle='--', label='Random')
plt.title('Accuracy Over Time (All Stocks)')
plt.show()
```

### Statistical Significance Test
```python
from scipy import stats

# Are sector differences statistically significant?
sectors = df.groupby('sector')['correct'].apply(list)

# One-way ANOVA
f_stat, p_value = stats.f_oneway(*sectors.values)
print(f"ANOVA p-value: {p_value:.4f}")

if p_value < 0.05:
    print("⚠️  Sectors have statistically different performance")
    print("   → Possible overfitting to specific sectors")
else:
    print("✓ Sector differences are not statistically significant")
    print("  → Good generalization")
```

---

## Troubleshooting

### "Insufficient training data" for some stocks
**Cause:** Stock has less historical data than others  
**Solution:** Use later holdout start (e.g., `--holdout-start 2025-11-01`)

### Validation takes too long
**Normal:** 1-3 min per stock, 15-30 min total for 8 stocks  
**Speed up:** Test fewer horizons (`--horizons 1D,5D`) or test 3 stocks first

### High variance across stocks
**Check:** Are some stocks fundamentally unpredictable?  
**Action:** Look at per-stock accuracy - is ALB (very volatile) dragging down average?  
**Decision:** May be OK if volatile stocks are harder (not overfitting)

---

## FAQ

**Q: Why these 8 stocks specifically?**

A: Covers diverse sectors/volatility without being too many (keeps runtime reasonable).  
   8 stocks × 60 days = 1,920 predictions gives statistical significance.

**Q: Should I add more stocks?**

A: Only if you want to test specific sectors. Diminishing returns after ~10 diverse stocks.

**Q: What if one sector performs badly?**

A: Two scenarios:
1. All volatile stocks perform badly → Model can't handle volatility (design decision)
2. One random sector bad → Overfitting or stock-specific issues (investigate)

**Q: Can I use this to select which stocks to trade?**

A: **NO!** That's using holdout data to make decisions (look-ahead bias).  
   Use for GO/NO-GO decision only. If you want stock selection, use separate optimization.

---

## Research Citations

- Diverse testing prevents overfitting: [web:107]
- Multi-asset backtesting: [web:111]  
- Statistical validation methods: [web:108]

---

## Next Steps After Validation

### If Results are Good (>55%, low variance)
1. ✅ Document validation results
2. ✅ Run shadow deployment (optional - tests infrastructure)
3. ✅ Deploy to production
4. ✅ Monitor performance on ALL stocks (not just test set)

### If Results Show Overfitting
1. Identify which group(s) perform well
2. Deploy only for those stocks/sectors
3. OR: Go back to development, retrain with balanced data
4. Re-validate with different holdout period

### If Results are Poor (<50%)
1. Check for bugs (data leakage, look-ahead bias)
2. Analyze feature importance
3. Test simpler baseline
4. **Do NOT deploy**
