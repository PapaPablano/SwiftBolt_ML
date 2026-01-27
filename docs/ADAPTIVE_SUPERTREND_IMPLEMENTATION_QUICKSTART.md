# AdaptiveSuperTrend Implementation Quick Start

**Goal**: Wire AdaptiveSuperTrend into forecast jobs in **2-3 hours**

**Status**: ✅ All supporting files created and ready

---

## 🚀 Quick Summary

Three new files have been created for you:

1. **Adapter**: `ml/src/strategies/adaptive_supertrend_adapter.py` (350 lines)
   - Ready-to-use wrapper around AdaptiveSuperTrend
   - Handles multi-timeframe, caching, consensus
   - Drop-in replacement for SuperTrendAI calls

2. **Integration Plan**: `ADAPTIVE_SUPERTREND_INTEGRATION_PLAN.md` (400 lines)
   - Complete strategy with phases and rollout
   - Testing checklist, monitoring, rollback plan
   - Success criteria and next steps

3. **Database Migration**: `supabase/migrations/20260126_adaptive_supertrend_integration.sql` (300 lines)
   - Extends `indicator_values` with adaptive columns
   - Creates 12 views for analysis and monitoring
   - Helper functions for queries

---

## 📋 Implementation Checklist

### Phase 1: Setup (30 minutes)

- [x] Adapter created: `ml/src/strategies/adaptive_supertrend_adapter.py`
- [x] Migration created: `supabase/migrations/20260126_*.sql`
- [x] Integration plan: `ADAPTIVE_SUPERTREND_INTEGRATION_PLAN.md`
- [ ] **TODO**: Add to `.env`:
  ```bash
  ENABLE_ADAPTIVE_SUPERTREND=false              # Feature flag (start disabled)
  ADAPTIVE_ST_OPTIMIZATION=true                 # Enable walk-forward
  ADAPTIVE_ST_CACHING=true                      # Enable Supabase cache
  ADAPTIVE_ST_CACHE_TTL_HOURS=24
  ADAPTIVE_ST_METRIC_OBJECTIVE=sharpe
  ```

### Phase 2: Code Integration (45 minutes)

#### Step 1: Update intraday_forecast_job.py

Find the imports section (around line 35-40):

```python
# Add this import
from src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter
```

Find the main signal generation loop (around line 200-250):

```python
# Replace or augment the SuperTrendAI call with:

if settings.get("ENABLE_ADAPTIVE_SUPERTREND", False):
    try:
        adapter = get_adaptive_supertrend_adapter()
        
        # Generate signals for all timeframes
        multi_tf_signals = await adapter.compute_multi_timeframe(
            symbol=symbol,
            ohlcv_data={
                "15m": df_15m,
                "1h": df_1h,
                "4h": df_4h,
            }
        )
        
        if multi_tf_signals:
            # Add to indicator values
            indicator_values.update({
                "adaptive_supertrend": multi_tf_signals,
                "supertrend_consensus": multi_tf_signals["consensus"]["bullish_score"],
            })
            
            # Also persist individual timeframe factors
            for tf, signal in multi_tf_signals["signals_by_timeframe"].items():
                indicator_values[f"supertrend_factor_{tf}"] = signal["factor"]
    
    except Exception as e:
        logger.error(f"AdaptiveSuperTrend error for {symbol}: {e}")
        # Fall through to SuperTrendAI if enabled

else:
    # Use original SuperTrendAI (keep existing code)
    supertrend_ai = SuperTrendAI(...)
    signals = supertrend_ai.compute(...)
```

#### Step 2: Update unified_forecast_job.py (if used)

Same pattern as intraday job:

```python
# Add import
from src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter

# Add feature-flagged call in signal generation
if settings.get("ENABLE_ADAPTIVE_SUPERTREND", False):
    adapter = get_adaptive_supertrend_adapter()
    signal = await adapter.compute_signal(
        symbol=symbol,
        ohlcv_df=df_daily,
        timeframe="1d"
    )
    # ... process signal
```

### Phase 3: Database Setup (15 minutes)

- [ ] **Apply migration**:
  ```bash
  # In Supabase dashboard or via CLI:
  supabase db push  # If using CLI
  
  # Or copy/paste SQL into Supabase SQL editor:
  # supabase/migrations/20260126_adaptive_supertrend_integration.sql
  ```

- [ ] **Verify tables updated**:
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

### Phase 4: Testing (30 minutes)

#### Unit Test

Create `ml/tests/test_adaptive_supertrend_adapter.py`:

```python
import pytest
import pandas as pd
from datetime import datetime, timedelta

from ml.src.strategies.adaptive_supertrend_adapter import (
    get_adaptive_supertrend_adapter,
    reset_adapter,
)


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'open': 100 + range(100),
        'high': 102 + range(100),
        'low': 99 + range(100),
        'close': 101 + range(100),
        'volume': 1000000,
    }, index=dates)
    return df


@pytest.mark.asyncio
async def test_compute_signal(sample_ohlcv):
    """Test basic signal computation."""
    reset_adapter()
    adapter = get_adaptive_supertrend_adapter()
    
    signal = await adapter.compute_signal(
        symbol="AAPL",
        ohlcv_df=sample_ohlcv,
        timeframe="1d"
    )
    
    assert signal is not None
    assert signal['symbol'] == "AAPL"
    assert signal['timeframe'] == "1d"
    assert 'factor' in signal
    assert 'confidence' in signal
    assert 'metrics' in signal


@pytest.mark.asyncio
async def test_compute_signal_insufficient_data():
    """Test handling of insufficient data."""
    reset_adapter()
    adapter = get_adaptive_supertrend_adapter()
    
    # Only 10 bars (need 50+)
    dates = pd.date_range('2023-01-01', periods=10, freq='D')
    df = pd.DataFrame({
        'open': 100 + range(10),
        'high': 102 + range(10),
        'low': 99 + range(10),
        'close': 101 + range(10),
        'volume': 1000000,
    }, index=dates)
    
    signal = await adapter.compute_signal(
        symbol="AAPL",
        ohlcv_df=df,
        timeframe="1d"
    )
    
    # Should return None for insufficient data
    assert signal is None


@pytest.mark.asyncio
async def test_multi_timeframe(sample_ohlcv):
    """Test multi-timeframe consensus computation."""
    reset_adapter()
    adapter = get_adaptive_supertrend_adapter()
    
    # Create data for multiple timeframes
    ohlcv_data = {
        "15m": sample_ohlcv,
        "1h": sample_ohlcv,
        "4h": sample_ohlcv,
    }
    
    result = await adapter.compute_multi_timeframe(
        symbol="AAPL",
        ohlcv_data=ohlcv_data
    )
    
    assert result is not None
    assert result['symbol'] == "AAPL"
    assert 'signals_by_timeframe' in result
    assert 'consensus' in result
    assert len(result['signals_by_timeframe']) == 3
    assert 0 <= result['consensus']['bullish_score'] <= 1


def test_singleton():
    """Test singleton pattern."""
    reset_adapter()
    
    adapter1 = get_adaptive_supertrend_adapter()
    adapter2 = get_adaptive_supertrend_adapter()
    
    # Should be same instance
    assert adapter1 is adapter2
```

Run test:

```bash
pytest ml/tests/test_adaptive_supertrend_adapter.py -v
```

#### Dry Run Test

```python
# Quick manual test in Python REPL

import asyncio
import pandas as pd
from datetime import datetime, timedelta

# Import adapter
from ml.src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter

# Create test data
dates = pd.date_range('2023-01-01', periods=100, freq='D')
df = pd.DataFrame({
    'open': 100 + range(100),
    'high': 102 + range(100),
    'low': 99 + range(100),
    'close': 101 + range(100),
    'volume': 1000000,
}, index=dates)

# Run test
async def test():
    adapter = get_adaptive_supertrend_adapter()
    signal = await adapter.compute_signal(
        symbol="TEST",
        ohlcv_df=df,
        timeframe="1d"
    )
    print(f"Signal: {signal}")
    return signal

result = asyncio.run(test())
print(f"Success! Factor: {result['factor']}, Confidence: {result['confidence']}")
```

### Phase 5: Staging Test (1 hour)

- [ ] **Set ENV in staging**:
  ```bash
  ENABLE_ADAPTIVE_SUPERTREND=true
  ```

- [ ] **Run intraday job for 1-2 symbols**:
  ```bash
  python ml/src/intraday_forecast_job.py --symbols AAPL MSFT
  ```

- [ ] **Check database**:
  ```sql
  SELECT symbol, supertrend_factor, supertrend_confidence, created_at
  FROM indicator_values
  WHERE supertrend_factor IS NOT NULL
  ORDER BY created_at DESC
  LIMIT 10;
  ```

- [ ] **Check cache**:
  ```sql
  SELECT * FROM adaptive_supertrend_cache
  WHERE expires_at > NOW()
  LIMIT 5;
  ```

- [ ] **Verify view**:
  ```sql
  SELECT * FROM adaptive_supertrend_factor_stats
  LIMIT 5;
  ```

- [ ] **Check logs** for errors:
  ```bash
  tail -f /var/log/forecast_job.log | grep -i adaptive
  ```

### Phase 6: Canary Prod (4-8 hours)

- [ ] **Deploy to production** (code only, flag still disabled)
- [ ] **Enable for single test symbol**:
  ```bash
  ENABLE_ADAPTIVE_SUPERTREND=true  # For CI/CD on one symbol
  ```
- [ ] **Monitor**:
  - Check logs: `tail -f /var/log/forecast_job.log`
  - Query signals: `SELECT * FROM adaptive_supertrend_latest_signals`
  - Check staleness: `SELECT * FROM adaptive_supertrend_staleness_check`
- [ ] **Compare results**:
  ```sql
  SELECT
    symbol,
    (metrics->>'sharpe_ratio')::float as sharpe,
    (metrics->>'sortino_ratio')::float as sortino,
    (metrics->>'calmar_ratio')::float as calmar,
    supertrend_factor
  FROM indicator_values
  WHERE supertrend_metrics IS NOT NULL
  ORDER BY created_at DESC
  LIMIT 20;
  ```

### Phase 7: Full Rollout (Day 2+)

- [ ] **Gradually increase coverage**:
  - 10% of symbols
  - 50% of symbols
  - 100% of symbols
- [ ] **Monitor performance metrics**:
  - Factor stability
  - Confidence levels
  - Sharpe ratio improvements
  - Error rates
- [ ] **Document results** in Slack/notes

---

## 📊 Key Queries

### Monitor signals

```sql
SELECT
    symbol,
    supertrend_factor,
    supertrend_confidence,
    supertrend_performance_index,
    supertrend_metrics->'sharpe_ratio' as sharpe,
    created_at
FROM indicator_values
WHERE supertrend_factor IS NOT NULL
AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

### Check cache health

```sql
SELECT
    symbol,
    COUNT(*) as cached_factors,
    MAX(updated_at) as last_update,
    EXTRACT(HOURS FROM NOW() - MAX(updated_at)) as hours_old
FROM adaptive_supertrend_cache
WHERE expires_at > NOW()
GROUP BY symbol
ORDER BY hours_old DESC;
```

### Compare factor stability

```sql
SELECT
    symbol,
    AVG(supertrend_factor) as avg_factor,
    MIN(supertrend_factor) as min_factor,
    MAX(supertrend_factor) as max_factor,
    STDDEV(supertrend_factor) as stddev_factor,
    AVG(supertrend_confidence) as avg_confidence,
    COUNT(*) as count
FROM indicator_values
WHERE supertrend_factor IS NOT NULL
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY stddev_factor DESC;
```

### Identify problems

```sql
SELECT * FROM adaptive_supertrend_anomalies;
```

### Performance improvements

```sql
SELECT
    symbol,
    AVG((supertrend_metrics->'sharpe_ratio')::float) as sharpe,
    AVG((supertrend_metrics->'sortino_ratio')::float) as sortino,
    AVG((supertrend_metrics->'total_return')::float) as return,
    COUNT(*) as signals
FROM indicator_values
WHERE supertrend_metrics IS NOT NULL
AND created_at > NOW() - INTERVAL '7 days'
GROUP BY symbol
ORDER BY sharpe DESC;
```

---

## 🎯 Success Metrics

You'll know it's working when:

- ✅ Adapter imports without errors
- ✅ Database migration applies cleanly
- ✅ First signal computed in < 100ms
- ✅ Signals stored in `indicator_values` table
- ✅ Cache table populated with factors
- ✅ Multi-timeframe consensus computed
- ✅ Sharpe ratio improved by +15-30% vs fixed factor
- ✅ Confidence scores > 0.6 on average
- ✅ Factor stability (STDDEV < 0.5)
- ✅ Zero errors for 24+ hours in staging
- ✅ Zero errors for 24+ hours in canary prod
- ✅ Ready for full rollout

---

## 🔧 Troubleshooting

### Error: ModuleNotFoundError: No module named 'adaptive_supertrend'

**Fix**: Install requirements

```bash
cd /Users/ericpeterson/SwiftBolt_ML
pip install -r adaptive_supertrend/requirements.txt
```

### Error: No signals computed

**Check**:
1. DataFrame has 50+ rows
2. Columns: open, high, low, close, volume
3. Index is datetime
4. Logs: `grep ERROR /var/log/forecast_job.log`

### Error: Supabase cache writes failing

**Check**:
1. Migration applied: `SELECT * FROM adaptive_supertrend_cache LIMIT 1`
2. Supabase credentials: `.env` has correct keys
3. Logs for auth errors

### Factors not changing daily

**Expected**: Factors should change slowly (±0.1-0.5 per day)
**Check**:
1. Walk-forward window is large enough (504 bars)
2. Test period is reasonable (252 bars)
3. Recent score decay working (exponential weighting)

---

## 📞 Next Steps

1. **Implement**: Follow checklist above (2-3 hours)
2. **Test**: Run unit tests + staging dry run (1 hour)
3. **Deploy**: Canary prod + gradual rollout (24-48 hours)
4. **Monitor**: Watch metrics, compare vs SuperTrendAI
5. **Document**: Record improvements and learnings

---

## 📚 References

- Full plan: `ADAPTIVE_SUPERTREND_INTEGRATION_PLAN.md`
- Adapter code: `ml/src/strategies/adaptive_supertrend_adapter.py`
- Migration: `supabase/migrations/20260126_adaptive_supertrend_integration.sql`
- Module docs: `adaptive_supertrend/README.md`
- Examples: `adaptive_supertrend/examples.py`

---

**Ready to go! Start with Phase 1 setup. ✅**
