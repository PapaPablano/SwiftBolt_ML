# Walk-Forward Validation: Findings and Next Steps

Consolidated summary of walk-forward results, interpretation, and recommended actions.

---

## 1. Current Results (Baseline RF, TSLA, 7 windows)

| Metric | Value | Benchmark | Status |
|--------|-------|-----------|--------|
| **Mean accuracy** | **30.3%** | 33.3% (random) | Below random |
| **Std deviation** | ±8.6% | <5% ideal | High variance |
| **Best window** | 42.0% | - | Only 1 strong period |
| **Worst window** | 16.0% | - | Very weak |
| **Overall** | 30.3% | - | Not production-ready |

Single-split validation had shown ~37.5%; that was effectively cherry-picking a favorable test period (Window 7: 42%). Walk-forward gives the honest picture.

---

## 2. What the Visualizations Show

### Accuracy by Test Window (Top-Left)

- Windows 1–2: 16%, 22% — model does not understand early regimes.
- Windows 3–4: 34%, 30% — around random.
- Windows 5, 7: 40%, 42% — only clearly good windows; Window 7 was the original single-split test set.

**Conclusion:** Performance is regime-dependent; not robust across market conditions.

### Accuracy Over Time – Expanding (Top-Right)

- Accuracy starts low (~10%) and rises to ~30% by the end.
- **Implication:** More training data helps. Early windows use only ~200 days; later windows use 400–500.
- **Action:** Try `initial_train_days` 300–400 and/or more total history (e.g. 1000+ days).

### Overall Confusion Matrix (Bottom-Left)

- Model predicts **neutral** only ~1.2% of the time (e.g. 5 of 412 predictions).
- Labels are balanced (percentile thresholds), but the model effectively avoids the neutral class.
- **Conclusion:** Common issue in 3-class financial forecasting; consider 2-class (bull vs bear) or regression.

### Distribution of Window Accuracies (Bottom-Right)

- Range 16%–42% (26 percentage points).
- **Conclusion:** Variance is too high for production; aim for mean >45%, std <5%, range <15 pp.

---

## 3. Root Causes

1. **Limited training data** — 200–300 days is tight; TabPFN and similar benefit from 400–800+ samples.
2. **Model avoids neutral** — Predictions are almost always bearish or bullish; neutral is underused.
3. **Features don’t encode regime** — Early windows fail, later ones improve; model lacks “what kind of market” context.
4. **Daily horizon** — Walk-forward with TabPFN on d1 is the right next test (implemented; TabPFN on CPU is slow).

---

## 4. Next Steps (Priority Order)

### Step 1: Run Walk-Forward with TabPFN (Done in code; run when you can)

- **Command:**  
  `python ml/analyze_walk_forward.py --symbol TSLA --initial-train-days 300 --test-days 50 --step-days 50`
- **Note:** TabPFN on CPU with >200 samples is slow; use GPU or allow long runtime (e.g. 10+ min per window).
- **Fix applied:** TabPFN returns continuous `y` (returns); walk-forward now converts test-set returns to labels using the model’s thresholds before computing accuracy.

**Interpretation:**

- **Scenario A:** Mean 45–55%, std <8% → TabPFN helps; consider production.
- **Scenario B:** Mean 32–38%, std 8–12% → Slight gain; still need feature/approach changes.
- **Scenario C:** Mean 28–35%, std 10–15% → TabPFN doesn’t fix it; rethink approach.

### Step 2: If TabPFN Isn’t Enough — Try 2-Class (Bull vs Bear)

- **Idea:** Drop “neutral”; only predict bearish vs bullish on clear moves (e.g. beyond ±threshold).
- **Baseline:** Random = 50%; target 55–65%.
- **Implementation:** In `prepare_training_data`, filter to `|forward_returns| > threshold` and use binary labels.

### Step 3: Add Regime Features

- **Idea:** Add “what kind of market” (e.g. SPY trend, VIX level, correlation to SPY, breadth).
- **Possible gains:** 30% → 38–45% with lower variance.
- **Effort:** ~2–3 hours (SPY/VIX load, align to symbol dates, add to feature set).

### Step 4: More Historical Data

- **Idea:** Use 1000+ days of history and/or `initial_train_days` 400.
- **Rationale:** Expanding-window plot suggests accuracy improves with more data.
- **Expected:** Better later-window performance; possibly mean 35–42%.

### Step 5: Regression Instead of Classification

- **Idea:** Predict next-period return (regression), then map to signal (e.g. bullish/bearish/neutral) via thresholds.
- **Benefits:** Uses full return distribution; no forced neutral avoidance.
- **Metrics:** MAE on returns + direction accuracy.

---

## 5. Summary Table

| Strategy | Expected mean acc | Std | Effort | Likelihood |
|----------|-------------------|-----|--------|------------|
| TabPFN (d1) | 42–55% | ±6–8% | Run (slow on CPU) | High |
| 2-class (bull vs bear) | 48–60% | ±5–7% | ~1 hr | High |
| Regime features | 38–48% | ±7–10% | ~3 hr | Medium |
| More data (e.g. 1000 days) | 35–42% | ±6–8% | ~30 min | Medium |
| Regression | 40–50% (MAE) | ±8–12% | ~2 hr | Medium |

---

## 6. Takeaways

1. **Single-split was optimistic** — True performance ~30.3% vs 37.5% from one split.
2. **High variance** — 16%–42% across windows; not robust.
3. **Neutral under-predicted** — Only ~1.2% neutral; consider 2-class or regression.
4. **More data helps** — Accuracy improves as training window grows (10% → 30% in the plot).
5. **Walk-forward is necessary** — It exposed regime dependence and overstatement from a single test period.

---

## 7. Files and Commands

- **Walk-forward module:** `ml/src/evaluation/walk_forward.py`  
  - `walk_forward_validate()` (expanding window), `walk_forward_rolling()` (rolling window).  
  - Supports both BaselineForecaster (labels) and TabPFNForecaster (returns → labels via thresholds).
- **CLI + plot:** `ml/analyze_walk_forward.py`  
  - `--symbol`, `--no-tabpfn`, `--initial-train-days`, `--test-days`, `--step-days`, `--no-plot`.
- **Example:**  
  `cd ml && python analyze_walk_forward.py --symbol TSLA --initial-train-days 300`  
  (TabPFN; allow long runtime on CPU or use GPU.)
