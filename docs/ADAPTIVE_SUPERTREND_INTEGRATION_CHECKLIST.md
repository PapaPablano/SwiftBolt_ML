# AdaptiveSuperTrend Integration Checklist

**Quick Start**: Follow this checklist to integrate AdaptiveSuperTrend into your forecast jobs.

**Estimated Time**: 2.5-3 hours (Phase 1-4) + deployment time

---

## Phase 1: Setup (30 minutes)

- [ ] **Add environment variables to `.env`**
  ```bash
  ENABLE_ADAPTIVE_SUPERTREND=false
  ADAPTIVE_ST_OPTIMIZATION=true
  ADAPTIVE_ST_CACHING=true
  ADAPTIVE_ST_CACHE_TTL_HOURS=24
  ADAPTIVE_ST_METRIC_OBJECTIVE=sharpe
  ```

- [ ] **Verify files exist**
  - [ ] `ml/src/strategies/adaptive_supertrend_adapter.py` (350 lines)
  - [ ] `adaptive_supertrend/` module is complete
  - [ ] `.env` ready for updates

- [ ] **Install dependencies** (if not already done)
  ```bash
  pip install -r adaptive_supertrend/requirements.txt
  ```

---

## Phase 2: Code Integration (45 minutes)

### Step 1: Update `ml/src/intraday_forecast_job.py`

- [ ] **Add import** (around line 35-40)
  ```python
  from src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter
  ```

- [ ] **Add adapter call** in main signal generation loop (feature-flagged)
  ```python
  if settings.get("ENABLE_ADAPTIVE_SUPERTREND", False):
      try:
          adapter = get_adaptive_supertrend_adapter()
          multi_tf_signals = await adapter.compute_multi_timeframe(
              symbol=symbol,
              ohlcv_data={
                  "15m": df_15m,
                  "1h": df_1h,
                  "4h": df_4h,
              }
          )
          if multi_tf_signals:
              indicator_values.update({
                  "adaptive_supertrend": multi_tf_signals,
                  "supertrend_consensus": multi_tf_signals["consensus"]["bullish_score"],
              })
      except Exception as e:
          logger.error(f"AdaptiveSuperTrend error: {e}")
  else:
      # Use original SuperTrendAI (keep existing code)
      ...
  ```

- [ ] **Verify fallback logic** - If flag is False, use SuperTrendAI as normal

### Step 2: Update `ml/src/unified_forecast_job.py` (if applicable)

- [ ] **Same pattern as intraday**: import adapter, add feature-flagged call

### Step 3: Code Review

- [ ] **Imports are clean**
- [ ] **Feature flag wraps all new code** (easy rollback)
- [ ] **Error handling present** (try/except with logging)
- [ ] **Existing code untouched** (fallback works)

---

## Phase 3: Database Setup (15 minutes)

- [ ] **Apply migration in Supabase**
  ```bash
  # Option A: Via Supabase CLI
  supabase db push
  
  # Option B: Copy-paste SQL
  # Open: supabase/migrations/20260126_adaptive_supertrend_integration.sql
  # Paste into Supabase SQL editor
  ```

- [ ] **Verify migration applied**
  ```sql
  SELECT column_name FROM information_schema.columns
  WHERE table_name = 'indicator_values'
  AND column_name LIKE 'supertrend_%';
  ```
  Should show:
  - supertrend_factor
  - supertrend_signal_strength
  - supertrend_confidence
  - supertrend_performance_index
  - supertrend_distance_pct
  - supertrend_trend_duration
  - supertrend_metrics

- [ ] **Verify views created**
  ```sql
  SELECT viewname FROM pg_views WHERE viewname LIKE 'adaptive%';
  ```
  Should show:
  - adaptive_supertrend_latest_signals
  - adaptive_supertrend_factor_stats
  - adaptive_supertrend_performance_stats
  - adaptive_supertrend_staleness_check
  - adaptive_vs_fixed_comparison
  - adaptive_supertrend_anomalies

---

## Phase 4: Testing (30 minutes)

### Unit Tests

- [ ] **Create test file**: `ml/tests/test_adaptive_supertrend_adapter.py`
  - Copy test patterns from `ADAPTIVE_SUPERTREND_IMPLEMENTATION_QUICKSTART.md`

- [ ] **Run tests**
  ```bash
  pytest ml/tests/test_adaptive_supertrend_adapter.py -v
  ```
  - [ ] test_compute_signal (should pass)
  - [ ] test_compute_signal_insufficient_data (should return None)
  - [ ] test_multi_timeframe (should compute consensus)
  - [ ] test_singleton (should reuse instance)

### Dry Run

- [ ] **Quick manual test**
  ```python
  import asyncio
  from ml.src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter
  
  adapter = get_adaptive_supertrend_adapter()
  signal = await adapter.compute_signal("AAPL", test_df, "1d")
  print(f"Factor: {signal['factor']}, Confidence: {signal['confidence']}")
  ```

---

## Phase 5: Staging Test (1 hour)

- [ ] **Set env var**: `ENABLE_ADAPTIVE_SUPERTREND=true` (staging only)

- [ ] **Run intraday job with test symbols**
  ```bash
  python ml/src/intraday_forecast_job.py --symbols AAPL MSFT --dry-run
  ```

- [ ] **Check generated signals**
  ```sql
  SELECT symbol, supertrend_factor, supertrend_confidence, created_at
  FROM indicator_values
  WHERE supertrend_factor IS NOT NULL
  ORDER BY created_at DESC
  LIMIT 10;
  ```

- [ ] **Verify cache populated**
  ```sql
  SELECT symbol, supertrend_factor, updated_at
  FROM adaptive_supertrend_cache
  WHERE expires_at > NOW()
  LIMIT 5;
  ```

- [ ] **Check logs** for errors
  ```bash
  tail -f /var/log/forecast_job.log | grep -i adaptive
  ```
  - [ ] No ERROR or CRITICAL messages
  - [ ] INFO messages show signal computation

- [ ] **Verify data quality**
  - [ ] Factors in range 1.0-5.0 (mostly ~3.0)
  - [ ] Confidence scores 0-1
  - [ ] Metrics populated (Sharpe, Sortino, etc.)

---

## Phase 6: Canary Production (4-8 hours, monitoring)

- [ ] **Deploy code to production** (flag still disabled)
  ```bash
  git push && wait-for-deployment
  ```

- [ ] **Enable for SINGLE test symbol**
  ```bash
  # In production job, hardcode or use env:
  ENABLE_ADAPTIVE_SUPERTREND=true (for 1 symbol only)
  ```

- [ ] **Monitor for 1-2 hours**
  - [ ] Check logs: `tail -f /var/log/forecast_job.log`
  - [ ] Query signals: `SELECT * FROM adaptive_supertrend_latest_signals LIMIT 5`
  - [ ] Alert if errors > 1%

- [ ] **If successful, expand to 10% of symbols**
  - [ ] Monitor 4-6 more hours
  - [ ] Compare Sharpe vs baseline SuperTrendAI

- [ ] **If successful, expand to 50% of symbols**
  - [ ] Monitor 24 hours
  - [ ] Check factor stability (STDDEV < 0.5)

---

## Phase 7: Full Rollout (24-48 hours)

- [ ] **Set `ENABLE_ADAPTIVE_SUPERTREND=true` for 100% of symbols**

- [ ] **Monitor continuously**
  - [ ] Factor variance: `SELECT stddev_factor FROM adaptive_supertrend_factor_stats`
  - [ ] Confidence: `SELECT avg_confidence FROM adaptive_supertrend_factor_stats`
  - [ ] Performance: `SELECT avg_sharpe FROM adaptive_supertrend_performance_stats`

- [ ] **Compare metrics**
  ```sql
  SELECT * FROM adaptive_vs_fixed_comparison
  ORDER BY adaptive_sharpe DESC;
  ```

- [ ] **Document results**
  - [ ] Sharpe improvement: ____%
  - [ ] Sortino improvement: ____%
  - [ ] Factor stability: ____
  - [ ] Issues/notes: ___________

---

## Success Criteria

✅ **Integration Complete When:**

- [ ] Adapter imports without errors
- [ ] Migration applies cleanly to Supabase
- [ ] Signals computed in < 100ms per symbol
- [ ] Multi-timeframe consensus working
- [ ] Cache table populated with factors
- [ ] 24+ hours staging without errors
- [ ] 24+ hours canary prod (1 symbol) without errors
- [ ] Sharpe ratio +15-30% vs fixed factor
- [ ] Factor confidence > 0.6 on average
- [ ] Factor stability STDDEV < 0.5
- [ ] Ready for full rollout ✅

---

## Rollback Plan (If Issues)

**Immediate Rollback** (< 5 minutes):
- [ ] Set `ENABLE_ADAPTIVE_SUPERTREND=false` in env
- [ ] Restart forecast job
- [ ] Reverts to SuperTrendAI immediately
- [ ] No data loss

**Investigate**:
- [ ] Check logs: `grep ERROR /var/log/forecast_job.log`
- [ ] Query anomalies: `SELECT * FROM adaptive_supertrend_anomalies`
- [ ] Verify data quality

**Root Cause Analysis**:
- [ ] Data issues (insufficient bars, missing columns)?
- [ ] Configuration (env vars set correctly)?
- [ ] Adapter code (exceptions in compute_signal)?
- [ ] Database (migration not applied, columns missing)?

---

## Key Commands

### Testing
```bash
pytest ml/tests/test_adaptive_supertrend_adapter.py -v
pytest ml/tests/test_adaptive_supertrend_adapter.py::test_compute_signal -v
```

### Database Queries
```sql
-- Latest signals
SELECT * FROM adaptive_supertrend_latest_signals LIMIT 5;

-- Factor statistics
SELECT * FROM adaptive_supertrend_factor_stats LIMIT 5;

-- Performance metrics
SELECT * FROM adaptive_supertrend_performance_stats LIMIT 5;

-- Staleness check
SELECT * FROM adaptive_supertrend_staleness_check WHERE staleness_status != 'HEALTHY';

-- Anomalies
SELECT * FROM adaptive_supertrend_anomalies;

-- Performance comparison
SELECT * FROM adaptive_vs_fixed_comparison ORDER BY adaptive_sharpe DESC;
```

### Monitoring
```bash
# Watch logs
tail -f /var/log/forecast_job.log | grep -i adaptive

# Check job status
pgrep -f intraday_forecast_job  # Should show PID

# Recent signals count
psql -d swiftbolt -c "SELECT COUNT(*) FROM indicator_values WHERE supertrend_factor IS NOT NULL AND created_at > NOW() - INTERVAL '1 hour';"
```

---

## Documentation References

- **Full Integration Plan**: `ADAPTIVE_SUPERTREND_INTEGRATION_PLAN.md`
- **Quick Start Guide**: `ADAPTIVE_SUPERTREND_IMPLEMENTATION_QUICKSTART.md`
- **Build Summary**: `ADAPTIVE_SUPERTREND_BUILD_SUMMARY.md`
- **Adapter Code**: `ml/src/strategies/adaptive_supertrend_adapter.py`
- **Migration**: `supabase/migrations/20260126_adaptive_supertrend_integration.sql`
- **Module Docs**: `adaptive_supertrend/README.md`
- **Examples**: `adaptive_supertrend/examples.py`

---

**Start with Phase 1 → Phase 4 today (3 hours). Deploy & monitor Phase 5-7 over next 2-3 days. 🚀**
