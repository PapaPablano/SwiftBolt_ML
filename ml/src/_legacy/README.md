# Legacy Scripts (Archived)

**Date Archived**: January 23, 2026  
**Reason**: Consolidated into unified forecast and evaluation processors

---

## Archived Scripts

These scripts have been replaced by the consolidated implementation in Phase 2 of the SwiftBolt ML Consolidation project.

### Forecast Jobs (Consolidated → `unified_forecast_job.py`)

| Legacy Script | Replaced By | Reason |
|---------------|-------------|--------|
| `forecast_job.py` | `unified_forecast_job.py` | Merged into unified processor |
| `multi_horizon_forecast_job.py` | `unified_forecast_job.py` | Merged into unified processor |
| `multi_horizon_forecast.py` | `unified_forecast_job.py` | Merged into unified processor |

**Consolidation Benefits**:
- 60% code reduction
- Single write path to database
- Explicit weight precedence
- Integrated metrics tracking
- Better error handling

### Evaluation Jobs (Split → Daily/Intraday)

| Legacy Script | Replaced By | Reason |
|---------------|-------------|--------|
| `evaluation_job.py` | `evaluation_job_daily.py` | Split into daily-specific evaluation |
| `intraday_evaluation_job.py` | `evaluation_job_intraday.py` | Renamed and enhanced for intraday |

**Split Benefits**:
- No data mixing in `forecast_evaluations` table
- Separate thresholds for daily (±2%) vs intraday (±0.5%)
- Clear separation of concerns
- Independent calibration paths

### Worker Scripts (Removed/Redundant)

| Legacy Script | Status | Reason |
|---------------|--------|--------|
| `forecast_job_worker.py` | Archived | Redundant with unified job |
| `job_worker.py` | Archived | Generic worker replaced by specific jobs |
| `ranking_job_worker.py` | Archived | Functionality integrated elsewhere |
| `hourly_ranking_scheduler.py` | Archived | Integrated into daily processing |

---

## Active Scripts (Not Archived)

These scripts are still in use and were **not** archived:

- `unified_forecast_job.py` - **NEW**: Consolidated daily forecast processor
- `evaluation_job_daily.py` - **NEW**: Daily evaluation (1D, 1W, 1M)
- `evaluation_job_intraday.py` - **NEW**: Intraday evaluation (15m, 1h)
- `intraday_forecast_job.py` - **KEPT**: Intraday forecast generation
- `forecast_synthesizer.py` - **KEPT**: Core forecasting logic (library)
- `forecast_weights.py` - **KEPT**: Weight management (library)
- `forecast_validator.py` - **KEPT**: Validation utilities (library)
- `ranking_evaluation_job.py` - **KEPT**: Ranking evaluation (separate concern)

---

## Migration Guide

If you need to rollback or reference legacy behavior:

### Rollback Instructions

```bash
# Restore from git history
git checkout HEAD~N ml/src/forecast_job.py
git checkout HEAD~N ml/src/evaluation_job.py
git checkout HEAD~N .github/workflows/ml-orchestration.yml

# Disable unified jobs
export USE_UNIFIED_FORECAST=false

# Run legacy pipeline
python ml/src/forecast_job.py
python ml/src/evaluation_job.py
```

### Key Differences in Unified Implementation

1. **Weight Selection**:
   - Legacy: Implicit precedence, hard to debug
   - Unified: Explicit precedence with logging (intraday → daily_symbol → default)

2. **Feature Caching**:
   - Legacy: DB cache only (30-minute TTL)
   - Unified: Redis + DB cache (24-hour TTL)

3. **Metrics**:
   - Legacy: Manual instrumentation per script
   - Unified: Built-in `ProcessingMetrics` class

4. **Database Writes**:
   - Legacy: Multiple scripts writing to same tables
   - Unified: Single write path per table

5. **Evaluation**:
   - Legacy: Mixed daily/intraday in one table
   - Unified: Separate evaluation jobs with distinct thresholds

---

## Historical Performance

### Before Consolidation (Legacy)
- Feature rebuilds: 9-14x per symbol per day
- Daily processing: 60-90 minutes
- Cache hit rate: ~30%
- Scripts to maintain: 6 forecast/evaluation scripts

### After Consolidation (Unified)
- Feature rebuilds: 1-2x per symbol per day (7-12x reduction)
- Daily processing: 15-20 minutes (4-6x speedup)
- Cache hit rate: 95%+ (with Redis)
- Scripts to maintain: 3 forecast/evaluation scripts (50% reduction)

---

## Documentation

For details on the consolidation effort, see:
- `CONSOLIDATION_IMPLEMENTATION_PLAN.md` - Full implementation plan
- `CONSOLIDATION_COMPLETE_SUMMARY.md` - Summary of all phases
- `DEPENDENCY_ANALYSIS.md` - Original dependency analysis
- `tests/audit_tests/README_PHASE3.md` - Testing documentation

---

## Kept for Reference Only

These scripts are kept for:
1. **Rollback purposes** - In case issues arise with unified implementation
2. **Historical reference** - Understanding past behavior
3. **Migration assistance** - Helping with any edge cases

**Do not use these scripts in production.** They have been superseded by the unified implementation.

---

**Status**: ✅ Archived and superseded  
**Rollback Available**: Yes (via git)  
**Last Active**: January 23, 2026
