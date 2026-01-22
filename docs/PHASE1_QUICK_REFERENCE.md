# Phase 1 Quick Reference

**Status**: ✅ COMPLETE  
**Date**: January 22, 2026

---

## What You Can Do Now

### 1. Run Validation for Any Symbol

```python
from src.services.validation_service import ValidationService

service = ValidationService()
result = await service.get_live_validation("AAPL", "BULLISH")

print(f"Confidence: {result.unified_confidence:.1%}")
print(f"Drift: {result.drift_severity}")
print(f"Recommendation: {result.recommendation}")
```

### 2. Test the Implementation

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python ml/src/services/test_validation_service.py
```

### 3. Query Validation Results

```sql
-- Get latest validation for each symbol
SELECT * FROM latest_validation_results;

-- Get symbols with drift
SELECT symbol, drift_severity, drift_magnitude, drift_explanation
FROM validation_results
WHERE drift_detected = true
ORDER BY drift_magnitude DESC;

-- Get symbols needing retraining
SELECT symbol, retraining_reason, unified_confidence
FROM validation_results
WHERE retraining_trigger = true
ORDER BY created_at DESC;
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ml/src/services/validation_service.py` | Main validation service |
| `ml/src/services/test_validation_service.py` | Test suite |
| `supabase/migrations/20260122000000_create_validation_results.sql` | Database schema |
| `docs/PHASE1_COMPLETION_SUMMARY.md` | Detailed implementation notes |

---

## Integration Checklist

Phase 1 provides:
- ✅ Real-time metric fetching from database
- ✅ Score reconciliation via UnifiedValidator
- ✅ Drift detection and severity classification
- ✅ Multi-timeframe conflict resolution
- ✅ Database storage of validation results
- ✅ Comprehensive error handling

Phase 2 will add:
- ⏳ REST API endpoints
- ⏳ Swagger documentation
- ⏳ History queries
- ⏳ Drift alert endpoints

Phase 3 will add:
- ⏳ Dashboard UI integration
- ⏳ Real-time charts
- ⏳ Alert notifications

---

## Quick Test Result

```
Symbol: AAPL
Direction: BULLISH
Unified Confidence: 47.2% 🟠

Component Scores:
  Backtesting: 55.0%
  Walk-forward: 60.0%
  Live: 50.0%

Drift Analysis:
  Detected: False
  Magnitude: 9.1%
  Severity: none

Recommendation: Low confidence - consider reduced position size
```

---

## Next Steps

Ready to implement Phase 2? Run:

```bash
# Start Phase 2 implementation
# See: docs/IMPLEMENTATION_CHECKLIST.md - Phase 2
```

---

## Troubleshooting

### Issue: Database connection fails

**Solution**: Ensure `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`

### Issue: No data returned (default values used)

**Solution**: Populate tables with test data:
- `model_validation_stats` - Add backtesting/walkforward scores
- `live_predictions` - Add recent predictions
- `indicator_values` - Add multi-TF indicator scores

### Issue: Import errors

**Solution**: 
```bash
cd ml
pip install -r requirements.txt
```

---

## Support

- Full documentation: `docs/PHASE1_COMPLETION_SUMMARY.md`
- Implementation plan: `docs/IMPLEMENTATION_CHECKLIST.md`
- Validation framework: `docs/VALIDATION_IMPLEMENTATION_ROADMAP.md`
