# Model Weight Verification Guide

This guide explains how to verify that your `symbol_model_weights` table and intraday calibration system are functioning correctly.

---

## Quick Reference

### Table Structure

```sql
symbol_model_weights (
    id uuid,
    symbol_id uuid,
    horizon text,
    rf_weight numeric,              -- Legacy model weights
    gb_weight numeric,
    synth_weights jsonb,            -- ⭐ Contains layer weights
    diagnostics jsonb,
    calibration_source varchar(50), -- 'daily' or 'intraday'
    intraday_sample_count integer,
    intraday_accuracy numeric,
    last_updated timestamptz,
    created_at timestamptz
)
```

### Layer Weights Structure (Inside `synth_weights`)

```json
{
  "layer_weights": {
    "supertrend_component": 0.35,
    "sr_component": 0.30,
    "ensemble_component": 0.35
  }
}
```

⚠️ **Important:** The three components should sum to approximately 1.0.

---

## Verification Methods

### Method 1: Python Script (Recommended)

#### Quick Check for Single Symbol

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
python scripts/verify_model_weights.py --symbol AAPL
```

#### Full Analysis with Calibration Stats

```bash
python scripts/verify_model_weights.py --symbol NVDA --calibration --evaluations
```

#### System Health Overview

```bash
python scripts/verify_model_weights.py --health
```

#### Verify All Symbols

```bash
python scripts/verify_model_weights.py --all
```

#### Available Options

| Option | Description |
|--------|-------------|
| `--symbol TICKER` | Check specific symbol (e.g., AAPL, NVDA) |
| `--horizon HORIZON` | Filter by horizon (e.g., 1D, 15m, 1h) |
| `--calibration` | Show intraday calibration statistics |
| `--evaluations` | Show recent forecast evaluations |
| `--health` | Show system health metrics |
| `--all` | Verify all symbols in database |

---

### Method 2: SQL Queries (Supabase)

Run the queries in `/scripts/verify_weights.sql` in your Supabase SQL Editor.

#### Essential Queries

**1. View All Weights with Structure Validation**

```sql
SELECT 
    s.ticker,
    smw.horizon,
    (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric AS st_weight,
    (smw.synth_weights->'layer_weights'->>'sr_component')::numeric AS sr_weight,
    (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS ensemble_weight,
    smw.intraday_accuracy,
    smw.last_updated
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
ORDER BY s.ticker, smw.horizon;
```

**2. Check Weight Sum Validation**

```sql
WITH weight_sums AS (
    SELECT 
        s.ticker,
        smw.horizon,
        (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric +
        (smw.synth_weights->'layer_weights'->>'sr_component')::numeric +
        (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS total
    FROM symbol_model_weights smw
    JOIN symbols s ON s.id = smw.symbol_id
)
SELECT 
    ticker,
    horizon,
    ROUND(total::numeric, 4) AS weight_sum,
    CASE 
        WHEN ABS(total - 1.0) <= 0.01 THEN '✅ Valid'
        ELSE '❌ Invalid: off by ' || ROUND(ABS(total - 1.0)::numeric, 4)::text
    END AS status
FROM weight_sums;
```

**3. Get Calibration Data for Symbol**

```sql
SELECT * FROM get_intraday_calibration_data(
    (SELECT id FROM symbols WHERE ticker = 'AAPL'),
    72  -- lookback hours
);
```

**4. Component Accuracy Summary**

```sql
SELECT 
    s.ticker,
    e.horizon,
    COUNT(*) AS evals,
    ROUND(AVG(CASE WHEN e.direction_correct THEN 1 ELSE 0 END)::numeric, 3) AS accuracy,
    ROUND(AVG(CASE WHEN e.supertrend_direction_correct THEN 1 ELSE 0 END)::numeric, 3) AS st_accuracy,
    ROUND(AVG(CASE WHEN e.sr_containment THEN 1 ELSE 0 END)::numeric, 3) AS sr_containment,
    ROUND(AVG(CASE WHEN e.ensemble_direction_correct THEN 1 ELSE 0 END)::numeric, 3) AS ensemble_accuracy
FROM ml_forecast_evaluations_intraday e
JOIN symbols s ON s.id = e.symbol_id
WHERE e.evaluated_at >= NOW() - INTERVAL '72 hours'
GROUP BY s.ticker, e.horizon;
```

---

## What to Look For

### ✅ Healthy Weights

1. **Structure is valid**
   - `synth_weights` contains `layer_weights` key
   - All three components present: `supertrend_component`, `sr_component`, `ensemble_component`

2. **Weight constraints**
   - Each component is between 0.0 and 1.0
   - Components sum to ~1.0 (within 0.01 tolerance)

3. **Calibration freshness**
   - `last_updated` within last 7 days
   - `intraday_sample_count > 0` if using intraday calibration
   - `intraday_accuracy` is reasonable (> 0.5)

4. **Evaluation coverage**
   - Recent evaluations exist (last 24-72 hours)
   - Component accuracies are balanced
   - No single component dominates excessively

### ❌ Common Issues

1. **Missing layer_weights key**
   - **Cause:** Old data or migration not applied
   - **Fix:** Re-run calibration or update weights manually

2. **Weights don't sum to 1.0**
   - **Cause:** Calibration algorithm issue or manual entry error
   - **Fix:** Re-calibrate or normalize weights

3. **Stale weights (not updated in > 7 days)**
   - **Cause:** Calibration job not running
   - **Fix:** Check scheduled jobs, run manual calibration

4. **Zero intraday_sample_count**
   - **Cause:** No evaluations or intraday forecasts
   - **Fix:** Verify intraday forecast generation is working

5. **Component accuracy imbalance (one < 0.4 while others > 0.6)**
   - **Cause:** One layer performing poorly
   - **Fix:** Investigate the underperforming component

---

## Verification Checklist

### Daily Checks

- [ ] Run `python scripts/verify_model_weights.py --health`
- [ ] Check that evaluations are being created (last 24h count > 0)
- [ ] Verify pending forecasts are being processed

### Weekly Checks

- [ ] Review weight freshness for all symbols
- [ ] Check calibration accuracy trends
- [ ] Verify component balance (no extreme dominance)
- [ ] Review evaluation accuracy by horizon

### Monthly Audits

- [ ] Run full verification: `--all` flag
- [ ] Check for structural issues across all symbols
- [ ] Analyze component accuracy trends over time
- [ ] Review weight distribution statistics

---

## Troubleshooting

### No Weights Found for Symbol

```bash
# Check if symbol exists
psql $SUPABASE_URL -c "SELECT * FROM symbols WHERE ticker = 'AAPL';"

# Check if weights table is populated
psql $SUPABASE_URL -c "SELECT COUNT(*) FROM symbol_model_weights;"

# Manually insert test weights if needed (development only)
INSERT INTO symbol_model_weights (symbol_id, horizon, synth_weights)
VALUES (
    (SELECT id FROM symbols WHERE ticker = 'AAPL'),
    '1D',
    '{
        "layer_weights": {
            "supertrend_component": 0.33,
            "sr_component": 0.33,
            "ensemble_component": 0.34
        }
    }'::jsonb
);
```

### Invalid Weight Structure

```sql
-- Find entries with issues
SELECT 
    s.ticker,
    smw.horizon,
    smw.synth_weights
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
WHERE NOT (smw.synth_weights ? 'layer_weights');

-- Fix structure (update to correct format)
UPDATE symbol_model_weights
SET synth_weights = jsonb_build_object(
    'layer_weights', jsonb_build_object(
        'supertrend_component', 0.33,
        'sr_component', 0.33,
        'ensemble_component', 0.34
    )
)
WHERE NOT (synth_weights ? 'layer_weights');
```

### No Recent Evaluations

```bash
# Check if intraday forecasts are being generated
SELECT COUNT(*) FROM ml_forecasts_intraday
WHERE created_at >= NOW() - INTERVAL '24 hours';

# Check for pending evaluations
SELECT * FROM get_pending_intraday_evaluations();

# Manually trigger evaluation job (if exists)
# Check your job scheduler or worker process
```

### Calibration Not Running

```bash
# Check job definitions
SELECT * FROM job_definitions WHERE job_type LIKE '%calibrat%';

# Check recent job runs
SELECT * FROM job_runs 
WHERE job_type LIKE '%calibrat%'
ORDER BY started_at DESC
LIMIT 10;

# Check for errors in job runs
SELECT * FROM job_runs
WHERE status = 'failed'
    AND job_type LIKE '%calibrat%'
ORDER BY started_at DESC;
```

---

## Understanding the Output

### Python Script Output Example

```
======================================================================
Model Weights for AAPL
======================================================================

Horizon: 1D
Last Updated: 2026-01-24 14:30:00+00:00
Calibration Source: intraday
Intraday Samples: 48
Intraday Accuracy: 0.6458

✅ Weight Structure: VALID

Layer Weights:
  SuperTrend Component:  0.3500
  S/R Component:         0.3000
  Ensemble Component:    0.3500

  Total Weight Sum:      1.0000

----------------------------------------------------------------------
```

### Key Metrics Interpretation

| Metric | Good Range | Warning | Critical |
|--------|-----------|---------|----------|
| **Direction Accuracy** | > 0.55 | 0.45-0.55 | < 0.45 |
| **Avg Price Error** | < 2% | 2-5% | > 5% |
| **Component Accuracy** | > 0.50 | 0.40-0.50 | < 0.40 |
| **Intraday Sample Count** | > 20 | 10-20 | < 10 |
| **Weight Sum** | 0.99-1.01 | 0.97-0.99 or 1.01-1.03 | Outside |
| **Weight Freshness** | < 24h | 24h-7d | > 7d |

---

## Integration with ML Pipeline

### Weight Update Flow

1. **Intraday Forecast Generation**
   - 15m/1h forecasts created and stored in `ml_forecasts_intraday`
   - Forecasts include component breakdowns

2. **Forecast Evaluation**
   - When `expires_at` is reached, evaluate forecast
   - Compare predicted vs actual prices
   - Store component-level accuracy in `ml_forecast_evaluations_intraday`

3. **Weight Calibration**
   - Aggregate recent evaluations (e.g., last 72 hours)
   - Calculate component accuracies
   - Optimize weights using evaluation data
   - Update `symbol_model_weights` table

4. **Weight Application**
   - New forecasts use updated weights
   - Components weighted according to recent performance
   - Continuous feedback loop

### Manual Calibration Trigger

```python
# If you need to manually trigger calibration
from src.services.calibration_service import CalibrationService

calibrator = CalibrationService()
calibrator.calibrate_symbol_weights(symbol="AAPL", horizon="1D")
```

---

## Related Files

- **Python Script:** `/ml/scripts/verify_model_weights.py`
- **SQL Queries:** `/scripts/verify_weights.sql`
- **Migration:** `/supabase/migrations/20260103120000_symbol_model_weights.sql`
- **Intraday System:** `/supabase/migrations/20260104200000_intraday_calibration.sql`
- **Weight Optimizer Tests:** `/ml/tests/test_weight_optimizer.py`

---

## Next Steps

1. Run initial verification: `python scripts/verify_model_weights.py --health`
2. Check specific symbols: `python scripts/verify_model_weights.py --symbol AAPL --calibration`
3. Set up automated health checks (add to cron/scheduler)
4. Create alerts for weight staleness or accuracy degradation
5. Monitor component balance over time

---

## Support

If you encounter issues not covered in this guide:

1. Check migration files for schema changes
2. Review database logs for errors
3. Verify job scheduler is running
4. Check Supabase dashboard for table structure
5. Run the test suite: `pytest ml/tests/test_weight_optimizer.py -v`
