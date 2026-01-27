# FORECASTING QUICK REFERENCE
## One-Page Cheat Sheet for Production Trading

**Last Updated:** January 2026  
**Version:** 1.0  
**For:** Daily model monitoring, quick troubleshooting, trading decisions

---

## PRIORITY CHECKLIST (Do This Every Morning)

### 9:15 AM Pre-Market
```
☐ Check email for overnight accuracy report
☐ Review yesterday's trades (winners/losers)
☐ Check model drift alert (accuracy drop >5%?)
☐ Verify API is responding (curl health endpoint)
☐ Check database size (no runaway logs?)
```

### 9:30 AM Market Open
```
☐ Run ensemble on top 10 holdings
☐ Any signals with confidence >70%?
☐ Compare to yesterday's signals (consistency?)
☐ Check S&P 500 direction (market context)
☐ Place first trades if confidence >65%
```

### 4:00 PM Market Close
```
☐ Log actual returns vs predictions
☐ Update accuracy tracker
☐ Any signals underperform? (adjust features?)
☐ Backup database
☐ Schedule next retraining (if monthly due)
```

---

## KEY METRICS AT A GLANCE

### Accuracy Benchmarks

| Metric | Target | Alert Level | Action |
|--------|--------|------------|--------|
| **Directional Accuracy** | 62%+ | <55% | Retrain all models |
| **Ensemble Confidence** | 65%+ avg | <50% | Use only high-confidence signals |
| **RMSE** | <0.015 | >0.025 | Reduce forecast horizon |
| **Sharpe Ratio** | 1.2+ | <0.8 | Reduce position size |
| **Max Drawdown** | -15% | <-25% | Stop trading, debug |
| **Win Rate** | 55%+ | <50% | Review position sizing |
| **Avg Winning Trade** | $500+ | <$100 | Raise min confidence threshold |
| **Avg Losing Trade** | <-$300 | <-$500 | Tighten stop losses |

### Daily Accuracy Report Template

```
Date: 2026-01-24

Training Accuracy (last 30 days):  64.2% ✓ GREEN
Today's Signals:                    8 trades
Today's Win Rate:                   62.5% (5/8)
Today's P&L:                        +$2,340 ✓ GREEN

Model Performance:
  - ARIMA:        58% accuracy (weight: 20%)
  - XGBoost:      63% accuracy (weight: 35%) ← BEST
  - LSTM:         59% accuracy (weight: 25%)
  - Transformer:  62% accuracy (weight: 20%)

Lowest Confidence Trade:   TSLA (48% - SKIP)
Highest Confidence Trade:  AAPL (82% - ENTER)

Stocks to Watch Tomorrow:
  - NVDA (Earnings priced in?)
  - AMZN (Support broken?)
  - SPY (Downtrend starting?)
```

---

## MODEL PERFORMANCE SHEET

### Current Accuracy by Model

```python
# Run this query daily
SELECT 
    model_type,
    COUNT(*) as predictions,
    ROUND(100.0 * SUM(CASE WHEN directional_correct THEN 1 ELSE 0 END) / COUNT(*), 2) as accuracy,
    ROUND(AVG(confidence), 3) as avg_confidence,
    ROUND(STDDEV(confidence), 3) as confidence_std
FROM model_results
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY model_type
ORDER BY accuracy DESC;
```

**Expected Output:**
```
model_type  | predictions | accuracy | avg_confidence | confidence_std
------------|-------------|----------|----------------|---------------
ensemble    |     150     |  64.2    |     0.68       |     0.15
xgboost     |     150     |  63.1    |     0.62       |     0.18
transformer |     150     |  62.4    |     0.65       |     0.16
lstm        |     150     |  59.8    |     0.61       |     0.20
arima       |     150     |  57.2    |     0.58       |     0.22
```

---

## QUICK TROUBLESHOOTING GUIDE

### Problem: Accuracy dropped 10%+ overnight

**Likely Causes (in order):**
1. Market regime change (earnings, Fed announcement)
2. Data quality issue (stock split, dividend)
3. Overfitting wearing off (retraining needed)
4. API returning stale data
5. Model drift from distribution shift

**Immediate Actions:**
```python
# Check recent accuracy by day
SELECT 
    DATE(created_at) as day,
    ROUND(100.0 * SUM(CASE WHEN directional_correct THEN 1 ELSE 0 END) / COUNT(*), 2) as accuracy
FROM predictions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY day DESC;

# Check for data gaps
SELECT symbol, COUNT(*) as days
FROM stock_prices
WHERE date > NOW() - INTERVAL '30 days'
GROUP BY symbol
HAVING COUNT(*) < 20;  -- Should be ~21 trading days

# Check VIX (high volatility = model struggles)
SELECT vix FROM macro_data WHERE date = TODAY();
```

**Decision Tree:**
```
Accuracy dropped?
├─ VIX > 30? → High volatility, reduce position size, skip low-confidence trades
├─ Recent earnings? → Regime change, increase training data weight
├─ Data gaps? → Fix data source, retrain
└─ Otherwise → Trigger immediate retraining on latest 12 months
```

### Problem: Model predicting same direction for all stocks

**Likely Cause:** Insufficient feature variance or model overfitting to market direction

**Check:**
```python
# Verify feature diversity
SELECT 
    symbol,
    direction,  -- 'UP' or 'DOWN'
    COUNT(*) as count
FROM predictions
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY symbol, direction;

# Should see mix of UP and DOWN across symbols
```

**Fix:**
```python
# Reduce learning rate, increase dropout
param_grid = {
    'learning_rate': 0.02,  # Down from 0.05
    'dropout': 0.3,         # Up from 0.2
    'max_depth': 3          # Reduce tree depth
}
```

### Problem: Confidence scores all clustered (50-55%)

**Likely Cause:** Models disagreeing (poor ensemble consensus)

**Fix:**
```python
# Reweight models by recent accuracy
new_weights = {
    'arima': 0.15,        # Reduce poor performers
    'xgboost': 0.40,      # Increase best performers
    'lstm': 0.25,
    'transformer': 0.20
}

# Verify: weighted accuracy should improve
ensemble_accuracy = (
    new_weights['arima'] * arima_acc +
    new_weights['xgboost'] * xgb_acc +
    new_weights['lstm'] * lstm_acc +
    new_weights['transformer'] * tf_acc
)
```

---

## TRADING DECISION RULES

### Entry Criteria

**ENTER if ALL of these are true:**
```
✓ Directional prediction confidence ≥ 65%
✓ Model agreement (≥3 of 4 models agree on direction)
✓ No earnings within 5 days
✓ Price not at 52-week extreme
✓ Volume trending normal to above average
✓ RSI not at extreme (>80 or <20)
✓ Portfolio not at 100% allocation
```

**Confidence Mapping:**
```
80%+ confidence → Position size: Full (3% risk)
70-79% confidence → Position size: Medium (2% risk)
65-69% confidence → Position size: Small (1% risk)
<65% confidence → SKIP this trade
```

### Exit Criteria

**EXIT if ANY of these triggers:**
```
✗ Stop loss hit (-1% to -3% depending on confidence)
✗ Take profit hit (+2% to +5% depending on horizon)
✗ Opposite signal appears with >75% confidence
✗ Time-based exit (hold 1-5 days based on horizon)
✗ Market closes, take remaining positions off
```

### Position Sizing Formula

```python
# Kelly Criterion modified for confidence
win_rate = 0.62
loss_ratio = 1.2  # avg win / avg loss
confidence = 0.72  # this trade's confidence

kelly_fraction = (win_rate - (1 - win_rate) / loss_ratio) / 1.0
position_size = kelly_fraction * confidence * portfolio_size

# Example: Portfolio $100k
position_size = 0.04 * 0.72 * 100000 = $2,880
```

---

## REALITY VS MARKETING CLAIMS

### What the Models Can Do ✓

```
✓ 60-65% directional accuracy (realistic)
✓ 1.2+ Sharpe ratio with proper risk management
✓ 5-20% annual returns with consistent trading
✓ Outperform buy-and-hold 70% of the time
✓ Reduce drawdowns vs passive investing
✓ Adapt to regime changes (with retraining)
✓ Work on liquid large-cap stocks (AAPL, TSLA, etc.)
```

### What the Models CANNOT Do ✗

```
✗ 90%+ accuracy (that's curve-fitting)
✗ Predict gap opens or earnings surprises
✗ Profit during market crashes (model breaks)
✗ Trade illiquid penny stocks (not enough data)
✗ Predict Black Swan events (model sees only history)
✗ Beat the market 100% of the time (impossible)
✗ Work without proper position sizing (risk control critical)
✗ Replace human judgment (always verify signals)
```

### Common Mistakes to Avoid

```
❌ WRONG: "64% accuracy = easy money"
✓ RIGHT: "64% accuracy with 1:2 risk/reward = tradeable"

❌ WRONG: "Use all 4 signals regardless of confidence"
✓ RIGHT: "Only trade confidence >65%, skip others"

❌ WRONG: "Retrain weekly (overfitting)"
✓ RIGHT: "Retrain monthly, monitor daily"

❌ WRONG: "Follow model blindly, no stops"
✓ RIGHT: "Use model for direction, risk management is critical"

❌ WRONG: "Test on 2024 data only"
✓ RIGHT: "Walk-forward validation on 5+ years data"

❌ WRONG: "Leverage 5:1 to amplify returns"
✓ RIGHT: "Normal leverage (1:1), maximize Sharpe not P&L"
```

---

## DAILY METRICS TO TRACK

### Performance Dashboard

```sql
-- This query gives you everything at 4:00 PM daily
WITH daily_trades AS (
    SELECT 
        DATE(created_at) as trade_date,
        symbol,
        direction,
        confidence,
        CASE WHEN directional_correct THEN 1 ELSE 0 END as correct
    FROM predictions
    WHERE created_at > NOW() - INTERVAL '30 days'
)
SELECT
    trade_date,
    COUNT(*) as total_trades,
    ROUND(100.0 * SUM(correct) / COUNT(*), 1) as accuracy,
    COUNT(CASE WHEN confidence > 0.70 THEN 1 END) as high_confidence_trades,
    COUNT(CASE WHEN correct = 1 AND confidence > 0.70 THEN 1 END) as high_conf_winners,
    ROUND(AVG(confidence), 2) as avg_confidence
FROM daily_trades
GROUP BY trade_date
ORDER BY trade_date DESC
LIMIT 30;
```

### Expected Daily Output

```
trade_date | trades | accuracy | high_conf | high_conf_wins | avg_conf
-----------|--------|----------|-----------|----------------|----------
2026-01-24 |   12   |  62.5%   |     8     |       6        |   0.68
2026-01-23 |   10   |  60.0%   |     6     |       4        |   0.65
2026-01-22 |   15   |  63.3%   |    10     |       7        |   0.69
2026-01-21 |    8   |  65.0%   |     6     |       5        |   0.72
2026-01-20 |   11   |  59.1%   |     7     |       4        |   0.63
```

---

## RETRAINING SCHEDULE

### Monthly Full Retraining (1st of month)

```bash
# 1. Backup current models
cp arima_current.pkl arima_backup_$(date +%Y%m%d).pkl
cp xgboost_current.json xgboost_backup_$(date +%Y%m%d).json

# 2. Fetch latest 12 months data
python fetch_data.py --days=252

# 3. Retrain all 4 models
python train_arima.py
python train_xgboost.py
python train_lstm.py
python train_transformer.py

# 4. Validate on most recent month
python validate_ensemble.py

# 5. If Sharpe > 1.0, deploy; otherwise keep backups
if [ $sharpe_ratio -gt 1.0 ]; then
    cp arima_current.pkl arima_prod.pkl
    # ... copy other models
else
    echo "New models underperform. Keeping current models."
fi
```

### Weekly Check (Every Monday)

```bash
# 1. Check model drift
python check_drift.py

# 2. If accuracy dropped >5%, flag for manual review
if [ $accuracy_drop -gt 0.05 ]; then
    send_email "Model drift detected. Review features."
fi
```

---

## FEATURE IMPORTANCE REFERENCE

### Top 10 Most Important Features (XGBoost)

```
1. RSI-14 (momentum)              15.2% importance
2. Distance from EMA-20 (trend)   12.8% importance
3. Volatility 20-day (risk)       11.4% importance
4. Volume Ratio (strength)        10.2% importance
5. MACD Histogram (momentum)        9.1% importance
6. ADX (trend strength)             8.7% importance
7. Bollinger Band Position          7.3% importance
8. Momentum 5-day (short-term)      6.8% importance
9. ATR Ratio (volatility)           6.2% importance
10. CCI-20 (mean reversion)         5.2% importance
```

**Implication:** Don't trade without calculating these features!

---

## WEEKLY REVIEW TEMPLATE

```markdown
# Weekly Review: Jan 20-24, 2026

## Results
- Total Trades: 52
- Win Rate: 63.5% (33 winners, 19 losers)
- Total P&L: +$4,250
- Sharpe Ratio: 1.18
- Max Drawdown: -$1,200 (-2.8%)

## Model Performance
- Ensemble Accuracy: 63.5% ✓
- XGBoost: 63.1% (best individual)
- LSTM: 59.8% (underperformed)
- ARIMA: 57.2% (reduce weight?)

## Wins This Week
- AAPL: +$850 (high confidence signals worked)
- TSLA: +$620 (momentum signals strong)
- SPY: +$480 (index tracking reliable)

## Losses This Week
- NVDA: -$450 (earnings surprised model)
- AMD: -$380 (gap down, model didn't predict)
- COIN: -$340 (low volume, illiquid)

## Actions for Next Week
1. Reduce LSTM weight (59.8% accuracy, dragging ensemble)
2. Skip earnings events (model unreliable 48h before/after)
3. Add volume filter (skip illiquid stocks)
4. Monitor ARIMA (consider dropping if <55%)
5. Increase high-confidence position size (working well)

## Outlook
- Market trending up, model performs well in trends
- VIX stable, volatility models predictable
- No major catalysts next week
- Recommend: Normal trading, high-confidence signals only
```

---

## EMERGENCY PROCEDURES

### If Accuracy Drops Below 50% (CIRCUIT BREAKER)

```
🚨 IMMEDIATE ACTIONS:
1. STOP all new trades
2. Close existing positions (market orders)
3. Check data quality (gaps, duplicates?)
4. Check market (circuit breaker? flash crash?)
5. Check models (any NaN outputs?)
6. Trigger emergency retraining
7. Review log files for errors

DO NOT:
✗ Keep trading (will amplify losses)
✗ Increase leverage (will make worse)
✗ Use models without validation
✗ Trade illiquid stocks (exit harder)
```

### If API Goes Down

```
1. Swift app shows "API Unavailable"
2. Check /health endpoint (curl http://api:8000/health)
3. If down:
   - Check AWS (is instance running?)
   - Check logs (ssh into instance, tail logs)
   - Restart service (systemctl restart swiftbolt)
4. If database down:
   - Restore from backup (today's snapshot)
   - Verify data integrity
   - Notify users of downtime
```

---

## FINAL TRADING RULES

```
1. TRUST THE DATA, NOT YOUR GUT
   - If confidence <65%, skip it
   - If model disagrees, investigate why

2. POSITION SIZE IS EVERYTHING
   - Risk management beats model accuracy
   - Use Kelly Criterion, not "all-in"

3. TRADE WITH THE TREND
   - Check SPY direction first (is market UP or DOWN?)
   - Model accuracy improves with trend alignment

4. NEVER PREDICT EARNINGS
   - Models break 48h before/after
   - Wait for dust to settle

5. DIVERSIFY ACROSS SYMBOLS
   - Don't put all capital in one stock
   - Spread trades across 10-15 positions

6. MONITOR CONTINUOUSLY
   - Check accuracy daily
   - Retrain monthly
   - Adjust weights quarterly

7. BE HUMBLE
   - Model is wrong 38% of the time
   - Losing streak is normal (math, not model)
   - Stay patient, compounding works
```

---

## QUICK COMMANDS

```bash
# Check API health
curl -s http://api.swiftbolt.local:8000/health | jq .

# Get latest prediction for AAPL
curl -s http://api.swiftbolt.local:8000/api/ensemble/forecast?symbol=AAPL | jq .

# Check today's accuracy
sqlite3 swiftbolt.db "SELECT COUNT(*), SUM(directional_correct) FROM predictions WHERE date(created_at) = date('now');"

# Trigger retraining
python train_all_models.py --days=252

# Monitor real-time P&L
watch -n 5 'sqlite3 swiftbolt.db "SELECT date(created_at), COUNT(*), SUM(pnl) FROM trades WHERE date(created_at) = date(now) GROUP BY 1;"'

# Backup database
cp swiftbolt.db swiftbolt_backup_$(date +%Y%m%d).db

# View model metrics
grep "Sharpe\|Accuracy\|Max Drawdown" daily_report.txt
```

---

**Remember:** This is a trading tool, not a trading strategy.
Adhere to proper risk management, position sizing, and stop losses.
The model guides direction. You control the trade.

