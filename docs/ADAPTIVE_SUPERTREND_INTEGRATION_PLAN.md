# AdaptiveSuperTrend Integration Plan

**Status**: Ready to wire into existing workflows  
**Date**: January 26, 2026  
**Owner**: SwiftBolt_ML

---

## 1. Executive Summary

The `adaptive_supertrend` module is **production-ready** and tested, but currently **not called** by any forecast jobs. This plan provides:

1. **Safe integration strategy** with environment flags
2. **Concrete code adapters** for intraday/daily jobs
3. **Database schema** for persistence
4. **Rollout checklist** for staged deployment

**Key Decision**: Replace `SuperTrendAI` with `AdaptiveSuperTrend` OR run both in parallel (A/B test)?  
**Recommendation**: Replace (simpler, cleaner), but feature-flag it for safe rollback.

---

## 2. Current State

### What Exists

| Component | Status | Location |
|-----------|--------|----------|
| AdaptiveSuperTrend module | ✅ Complete, tested | `adaptive_supertrend/` |
| SuperTrendAI | ✅ Currently used | `ml/src/strategies/supertrend_ai.py` |
| Intraday forecast job | ✅ Uses SuperTrendAI | `ml/src/intraday_forecast_job.py` |
| Daily forecast job | ✅ Uses SuperTrendAI | `ml/src/unified_forecast_job.py` |
| Supabase schema (adaptive_supertrend_cache) | ✅ Ready | SQL in `adaptive_supertrend/supabase_setup.sql` |
| Supabase schema (supertrend_signals) | ✅ Ready | SQL in `adaptive_supertrend/supabase_setup.sql` |

### Gap

- ❌ Intraday job doesn't import `AdaptiveSuperTrend`
- ❌ Daily job doesn't import `AdaptiveSuperTrend`
- ❌ Indicator snapshots don't capture adaptive factor/performance data
- ❌ No adapter layer (glue code)

---

## 3. Integration Architecture

### Option A: Full Replacement (Recommended)

```
Intraday Job (intraday_forecast_job.py)
    ↓
    uses AdaptiveSuperTrend (replaces SuperTrendAI)
    ↓
    Generates signals with adaptive factors
    ↓
    Persists to indicator_values + supertrend_signals
    ↓
    Gated by ENABLE_ADAPTIVE_SUPERTREND=true
```

**Pros**: Simpler, one code path, cleaner  
**Cons**: Need to revert if issues found

### Option B: Parallel A/B Test

```
Intraday Job splits signal computation:
    ├─ Path A: SuperTrendAI (old)
    └─ Path B: AdaptiveSuperTrend (new)
    ↓
Both store results to DB
↓
Compare metrics
```

**Pros**: Safe, can compare side-by-side  
**Cons**: More complex, duplicate computation

**Choice**: Start with **Option A + feature flag** = best of both (clean code + safe rollback)

---

## 4. Adapter Layer (New Module)

### File: `ml/src/strategies/adaptive_supertrend_adapter.py`

```python
"""
AdaptiveSuperTrend Adapter for Forecast Jobs

Provides a thin adapter between forecast job execution and AdaptiveSuperTrend.
Handles timeframe conversion, caching, and integration with existing indicator logic.
"""

import os
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime

import pandas as pd
import numpy as np

# Import AdaptiveSuperTrend from the module
from adaptive_supertrend import (
    AdaptiveSuperTrend,
    AdaptiveSuperTrendOptimizer,
    SuperTrendConfig,
    SuperTrendSignal,
    PerformanceMetrics,
)

logger = logging.getLogger(__name__)


class AdaptiveSuperTrendAdapter:
    """
    Adapter for integrating AdaptiveSuperTrend into forecast jobs.
    
    Handles:
    - Configuration from env variables
    - Multi-timeframe analysis
    - Caching with TTL
    - Integration with existing indicator snapshot format
    """

    def __init__(
        self,
        enable_caching: bool = True,
        cache_ttl_hours: int = 24,
        enable_optimization: bool = True,
    ):
        """
        Initialize adapter.
        
        Args:
            enable_caching: Use Supabase caching for factors
            cache_ttl_hours: TTL for cached factors
            enable_optimization: Run walk-forward optimization
        """
        self.enable_caching = enable_caching
        self.cache_ttl_hours = cache_ttl_hours
        self.enable_optimization = enable_optimization
        
        # Initialize AdaptiveSuperTrend
        config = SuperTrendConfig(
            atr_period=10,
            factor_min=1.0,
            factor_max=5.0,
            factor_step=0.5,
            lookback_window=504,  # 2 years at daily
            test_period=252,      # 1 year
            train_period=504,     # 2 years
            metric_objective='sharpe',
            cache_enabled=enable_caching,
            cache_ttl_hours=cache_ttl_hours,
        )
        
        self.ast = AdaptiveSuperTrend(config=config)
        self.logger = logging.getLogger(__name__)

    async def compute_signal(
        self,
        symbol: str,
        ohlcv_df: pd.DataFrame,
        timeframe: str = "1h",
        use_cached_factor: bool = True,
    ) -> Optional[Dict]:
        """
        Compute adaptive SuperTrend signal for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            ohlcv_df: DataFrame with OHLCV data
                      Must have columns: open, high, low, close, volume
                      Index: datetime
            timeframe: Timeframe identifier ("15m", "1h", "4h", "1d")
            use_cached_factor: Use cached optimal factor if available
        
        Returns:
            Dict with signal data, or None if signal generation failed
            
            Structure:
            {
                'symbol': str,
                'timeframe': str,
                'trend': int,           # 1 (bullish), 0 (bearish), -1 (unknown)
                'supertrend_value': float,
                'factor': float,        # Adaptive factor used
                'signal_strength': float,  # 0-10
                'confidence': float,    # 0-1
                'distance_pct': float,  # Distance from ST in %
                'trend_duration': int,  # Bars in trend
                'performance_index': float,  # 0-1, how well factor working
                'metrics': PerformanceMetrics,  # Full metrics if available
                'timestamp': datetime,
            }
        """
        try:
            if ohlcv_df is None or len(ohlcv_df) < 50:
                self.logger.warning(
                    f"Insufficient data for {symbol} {timeframe}: "
                    f"got {len(ohlcv_df) if ohlcv_df is not None else 0} rows"
                )
                return None
            
            # Run optimization if enabled
            if self.enable_optimization:
                signal = await self.ast.generate_signal_with_optimization(
                    symbol=symbol,
                    ohlcv_df=ohlcv_df,
                    timeframe=timeframe,
                    use_cached_factor=use_cached_factor,
                )
            else:
                # Use fixed factor (3.0, standard SuperTrend)
                signal = await self.ast.generate_signal(
                    symbol=symbol,
                    ohlcv_df=ohlcv_df,
                    factor=3.0,
                    timeframe=timeframe,
                )
            
            if signal is None:
                self.logger.warning(f"Failed to generate signal for {symbol}")
                return None
            
            # Convert to dict for database insertion
            return self._signal_to_dict(signal)
        
        except Exception as e:
            self.logger.error(
                f"Error computing signal for {symbol} {timeframe}: {e}",
                exc_info=True
            )
            return None

    def _signal_to_dict(self, signal: SuperTrendSignal) -> Dict:
        """
        Convert SuperTrendSignal to dict for database persistence.
        
        Returns dict with:
        - symbol, timeframe, timestamp
        - trend, supertrend_value
        - factor, signal_strength, confidence
        - distance_pct, trend_duration
        - performance_index
        - metrics (Sharpe, Sortino, Calmar, etc.)
        """
        result = {
            'symbol': signal.symbol,
            'timeframe': signal.timeframe,
            'timestamp': signal.timestamp.isoformat(),
            'trend': signal.trend,
            'supertrend_value': float(signal.supertrend_value),
            'factor': float(signal.factor),
            'signal_strength': float(signal.signal_strength),
            'confidence': float(signal.confidence),
            'distance_pct': float(signal.distance_pct),
            'trend_duration': int(signal.trend_duration),
            'performance_index': float(signal.performance_index),
        }
        
        # Add metrics if available
        if signal.metrics:
            result['metrics'] = {
                'sharpe_ratio': float(signal.metrics.sharpe_ratio),
                'sortino_ratio': float(signal.metrics.sortino_ratio),
                'calmar_ratio': float(signal.metrics.calmar_ratio),
                'max_drawdown': float(signal.metrics.max_drawdown),
                'win_rate': float(signal.metrics.win_rate),
                'profit_factor': float(signal.metrics.profit_factor),
                'total_return': float(signal.metrics.total_return),
                'num_trades': int(signal.metrics.num_trades),
                'recent_score': float(signal.metrics.recent_score),
            }
        
        return result

    async def compute_multi_timeframe(
        self,
        symbol: str,
        ohlcv_ Dict[str, pd.DataFrame],  # {"15m": df, "1h": df, "4h": df}
    ) -> Optional[Dict]:
        """
        Compute adaptive SuperTrend across multiple timeframes with consensus.
        
        Args:
            symbol: Stock symbol
            ohlcv_ Dict of timeframe -> OHLCV DataFrame
        
        Returns:
            Dict with signals for each timeframe + consensus scoring
        """
        try:
            signals_by_tf = {}
            
            for timeframe, df in ohlcv_data.items():
                signal_dict = await self.compute_signal(
                    symbol=symbol,
                    ohlcv_df=df,
                    timeframe=timeframe,
                    use_cached_factor=True,
                )
                if signal_dict:
                    signals_by_tf[timeframe] = signal_dict
            
            if not signals_by_tf:
                return None
            
            # Compute consensus
            bullish_count = sum(
                1 for s in signals_by_tf.values() if s['trend'] == 1
            )
            bearish_count = sum(
                1 for s in signals_by_tf.values() if s['trend'] == 0
            )
            total = len(signals_by_tf)
            
            consensus_score = bullish_count / total if total > 0 else 0.5
            
            # Avg metrics
            avg_confidence = np.mean([s['confidence'] for s in signals_by_tf.values()])
            avg_strength = np.mean([s['signal_strength'] for s in signals_by_tf.values()])
            
            return {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'signals_by_timeframe': signals_by_tf,
                'consensus': {
                    'bullish_score': float(consensus_score),
                    'bullish_count': bullish_count,
                    'bearish_count': bearish_count,
                    'total_timeframes': total,
                    'avg_confidence': float(avg_confidence),
                    'avg_strength': float(avg_strength),
                },
            }
        
        except Exception as e:
            self.logger.error(
                f"Error computing multi-timeframe signals for {symbol}: {e}",
                exc_info=True
            )
            return None


# Singleton for job usage
_adapter_instance: Optional[AdaptiveSuperTrendAdapter] = None


def get_adaptive_supertrend_adapter() -> AdaptiveSuperTrendAdapter:
    """
    Get or create singleton adapter instance.
    
    Usage:
        adapter = get_adaptive_supertrend_adapter()
        signal = await adapter.compute_signal("AAPL", ohlcv_df, "1h")
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = AdaptiveSuperTrendAdapter(
            enable_caching=os.getenv("ADAPTIVE_ST_CACHING", "true").lower() == "true",
            cache_ttl_hours=int(os.getenv("ADAPTIVE_ST_CACHE_TTL_HOURS", "24")),
            enable_optimization=os.getenv("ADAPTIVE_ST_OPTIMIZATION", "true").lower() == "true",
        )
    return _adapter_instance
```

---

## 5. Integration into Intraday Forecast Job

### File: `ml/src/intraday_forecast_job.py` (Changes)

**Add imports** (after line ~37):

```python
from src.strategies.adaptive_supertrend_adapter import get_adaptive_supertrend_adapter
```

**Update indicator computation** (in main loop, replace SuperTrendAI call):

```python
# OLD CODE (around line ~200-250):
# supertrend_ai = SuperTrendAI(...)
# signals = supertrend_ai.compute(...)

# NEW CODE:
if settings.get("ENABLE_ADAPTIVE_SUPERTREND", False):
    # Use adaptive SuperTrend with walk-forward optimization
    adapter = get_adaptive_supertrend_adapter()
    
    # Compute signals for all timeframes
    multi_tf_signals = await adapter.compute_multi_timeframe(
        symbol=symbol,
        ohlcv_data={
            "15m": df_15m,
            "1h": df_1h,
            "4h": df_4h,
        }
    )
    
    if multi_tf_signals:
        indicator_values = {
            **indicator_values,
            "adaptive_supertrend_signals": multi_tf_signals,
            "supertrend_factor_15m": multi_tf_signals["signals_by_timeframe"]["15m"].get("factor"),
            "supertrend_factor_1h": multi_tf_signals["signals_by_timeframe"]["1h"].get("factor"),
            "supertrend_factor_4h": multi_tf_signals["signals_by_timeframe"]["4h"].get("factor"),
        }
else:
    # Use original SuperTrendAI
    supertrend_ai = SuperTrendAI(...)
    signals = supertrend_ai.compute(...)
    # ... existing logic
```

---

## 6. Database Schema Updates

### File: `supabase/migrations/20260126_adaptive_supertrend_integration.sql`

```sql
-- Add adaptive SuperTrend columns to indicator_values
ALTER TABLE indicator_values
ADD COLUMN IF NOT EXISTS supertrend_factor FLOAT8,
ADD COLUMN IF NOT EXISTS supertrend_signal_strength FLOAT8,
ADD COLUMN IF NOT EXISTS supertrend_confidence FLOAT8,
ADD COLUMN IF NOT EXISTS supertrend_performance_index FLOAT8,
ADD COLUMN IF NOT EXISTS supertrend_distance_pct FLOAT8,
ADD COLUMN IF NOT EXISTS supertrend_metrics JSONB;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_indicator_values_symbol_supertrend_factor
ON indicator_values(symbol, supertrend_factor)
WHERE supertrend_factor IS NOT NULL;

-- Extend existing ml_forecasts to reference adaptive signals
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS adaptive_supertrend_consensus FLOAT8,
ADD COLUMN IF NOT EXISTS adaptive_supertrend_confidence FLOAT8;

-- Create view for recent adaptive signals
CREATE OR REPLACE VIEW adaptive_supertrend_latest_signals AS
SELECT
    symbol,
    supertrend_factor,
    supertrend_signal_strength,
    supertrend_confidence,
    supertrend_performance_index,
    supertrend_metrics,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY created_at DESC) as rn
FROM indicator_values
WHERE supertrend_factor IS NOT NULL;

-- Helper function to get latest adaptive factor for symbol
CREATE OR REPLACE FUNCTION get_latest_adaptive_supertrend_factor(p_symbol TEXT)
RETURNS FLOAT8 AS $$
SELECT supertrend_factor
FROM indicator_values
WHERE symbol = p_symbol
AND supertrend_factor IS NOT NULL
ORDER BY created_at DESC
LIMIT 1;
$$ LANGUAGE SQL STABLE;
```

---

## 7. Environment Configuration

### File: `.env` or `config/settings.py`

Add these settings:

```bash
# AdaptiveSuperTrend Integration
ENABLE_ADAPTIVE_SUPERTREND=true              # Main feature flag
ADAPTIVE_ST_OPTIMIZATION=true                # Enable walk-forward optimization
ADAPTIVE_ST_CACHING=true                     # Enable Supabase caching
ADAPTIVE_ST_CACHE_TTL_HOURS=24               # Cache expiration
ADAPTIVE_ST_METRIC_OBJECTIVE=sharpe          # sharpe|sortino|calmar
ADAPTIVE_ST_MIN_TRADES_FOR_EVAL=5            # Minimum trades to evaluate factor
```

### In `config/settings.py`:

```python
# Add to Settings class:
ENABLE_ADAPTIVE_SUPERTREND: bool = Field(
    default=False,
    description="Enable AdaptiveSuperTrend in forecast jobs"
)
ADAPTIVE_ST_OPTIMIZATION: bool = Field(
    default=True,
    description="Enable walk-forward optimization for factors"
)
ADAPTIVE_ST_CACHING: bool = Field(
    default=True,
    description="Enable Supabase caching of optimal factors"
)
ADAPTIVE_ST_CACHE_TTL_HOURS: int = Field(
    default=24,
    description="TTL for factor cache in hours"
)
ADAPTIVE_ST_METRIC_OBJECTIVE: str = Field(
    default="sharpe",
    description="Metric to optimize: sharpe|sortino|calmar"
)
```

---

## 8. Rollout Plan

### Phase 1: Staging (Day 1)

- [ ] Create `adaptive_supertrend_adapter.py`
- [ ] Run database migration in staging
- [ ] Test adapter with sample data
- [ ] Run `pytest tests/test_adaptive_supertrend_adapter.py`
- [ ] Set `ENABLE_ADAPTIVE_SUPERTREND=false` (disabled by default)

**Expected Duration**: 2-3 hours

### Phase 2: Dry Run (Day 2-3)

- [ ] Enable in staging job: `ENABLE_ADAPTIVE_SUPERTREND=true`
- [ ] Run 1 intraday forecast cycle
- [ ] Verify signals in Supabase (`adaptive_supertrend_cache` table)
- [ ] Compare signals: AdaptiveSuperTrend vs SuperTrendAI
- [ ] Check performance metrics

**Expected Duration**: 4-6 hours (includes analysis)

### Phase 3: Canary Prod (Day 4)

- [ ] Deploy to production with flag disabled
- [ ] Enable for 10% of symbols (ENABLE_ADAPTIVE_SUPERTREND=true for test symbols)
- [ ] Monitor logs for errors
- [ ] Check database inserts to `indicator_values`
- [ ] Run alerts for any failures

**Expected Duration**: 8-12 hours (continuous monitoring)

### Phase 4: Full Rollout (Day 5+)

- [ ] If canary successful, enable for 50% of symbols
- [ ] Monitor for 24 hours
- [ ] If stable, enable 100%
- [ ] Set `ENABLE_ADAPTIVE_SUPERTREND=true` in production
- [ ] Remove fallback to SuperTrendAI (or keep as escape hatch)

**Expected Duration**: 2-3 days (gradual increase)

---

## 9. Testing Checklist

### Unit Tests (`tests/test_adaptive_supertrend_adapter.py`)

```python
test_compute_signal_valid_data()
test_compute_signal_insufficient_data()
test_compute_signal_caching()
test_multi_timeframe_consensus()
test_adapter_singleton()
test_error_handling_bad_ohlcv()
test_performance_metrics_extraction()
```

### Integration Tests

```python
test_intraday_job_with_adaptive_st()  # Run full job with flag enabled
test_database_inserts()                # Verify indicator_values updated
test_supabase_cache_write()            # Check cache table populated
test_consensus_computation()           # Multi-timeframe signals
```

### Performance Tests

```python
test_compute_signal_speed()            # Should be ~50-100ms per signal
test_portfolio_performance()           # 50 symbols < 3 seconds
test_cache_hit_performance()           # <10ms for cached factors
```

---

## 10. Monitoring & Alerts

### Key Metrics to Monitor

1. **Signal Generation Time**
   - P95 latency per symbol
   - Portfolio (50) latency
   - Alert if > 200ms per symbol

2. **Cache Hit Rate**
   - % of signals using cached factors
   - Target: > 80%
   - Alert if < 50%

3. **Factor Variance**
   - Is adaptive factor changing daily?
   - Expected: ±0.5-1.0 around 3.0
   - Alert if static or wild swings

4. **Signal Quality**
   - Compare Sharpe vs SuperTrendAI
   - Expected: +15-30% improvement
   - Alert if degradation

5. **Error Rates**
   - % of failed signal generations
   - Target: < 0.1%
   - Alert if > 1%

### Supabase Queries

**Monitor signal generation**:

```sql
SELECT
    symbol,
    COUNT(*) as signal_count,
    AVG(supertrend_factor) as avg_factor,
    MIN(supertrend_factor) as min_factor,
    MAX(supertrend_factor) as max_factor,
    AVG(supertrend_confidence) as avg_confidence
FROM indicator_values
WHERE supertrend_factor IS NOT NULL
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY signal_count DESC;
```

**Check cache health**:

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

---

## 11. Rollback Plan

If issues occur:

1. **Immediate**: Set `ENABLE_ADAPTIVE_SUPERTREND=false` → reverts to SuperTrendAI
2. **Check logs**: `grep "ERROR" /var/log/forecast_job.log`
3. **Analyze signals**: Query `indicator_values` for anomalies
4. **Root cause**: Review adapter code, data issues, or config
5. **Fix & redeploy**: Update adapter, re-enable with flag

**Rollback Time**: < 5 minutes (config change)

---

## 12. Success Criteria

✅ **Integration Complete When**:

- [ ] Adapter module created and tested
- [ ] Intraday job imports adapter
- [ ] Database migration applied
- [ ] Signals saved to `indicator_values`
- [ ] Multi-timeframe consensus computed
- [ ] Cache table populated with factors
- [ ] Monitoring alerts in place
- [ ] Performance targets met
  - [ ] Signal generation: < 100ms per symbol
  - [ ] Portfolio (50): < 3 seconds
  - [ ] Cache hit rate: > 80%
- [ ] Staged rollout complete (day 5+)
- [ ] A/B testing shows +15-30% Sharpe improvement
- [ ] Zero production errors in 24-hour canary

---

## 13. Next Steps (Immediate)

1. **Create adapter** (`adaptive_supertrend_adapter.py`) - 30 min
2. **Update intraday job** with imports + feature flag - 30 min
3. **Run migration** in staging - 10 min
4. **Test adapter** with unit tests - 30 min
5. **Dry run** with sample symbols - 1 hour
6. **Documentation** update - 15 min

**Total**: ~2.5-3 hours to Phase 1 completion

---

## Questions?

Refer to:
- AdaptiveSuperTrend module: `adaptive_supertrend/README.md`
- Configuration: `config/settings.py`
- Migrations: `supabase/migrations/`
- Examples: `adaptive_supertrend/examples.py`
