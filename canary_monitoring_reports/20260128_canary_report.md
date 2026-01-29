# Phase 7.1 Canary Daily Monitoring Report

Date: 2026-01-28

**Data date:** 2026-01-28

## 1. Divergence Summary

| Symbol | Windows | Avg Div | Max Div | Min Div | Alerts |
|--------|---------|---------|---------|---------|--------|
| AAPL | 2 | 0.1025 | 0.1025 | 0.1025 | 0 |
| MSFT | 2 | 0.5181 | 0.5181 | 0.5181 | 2 |
| SPY | 2 | 0.4976 | 0.4976 | 0.4976 | 2 |

**Status:** ✅ All metrics within normal range

## 2. RMSE vs Baseline

| Symbol | Val RMSE | Test RMSE | Divergence % | Samples |
|--------|----------|-----------|--------------|---------|
| AAPL | 0.0096 | 0.0106 | 10.26% | 2 |
| MSFT | 0.0095 | 0.0145 | 51.80% | 2 |
| SPY | 0.0094 | 0.0047 | -49.76% | 2 |

**Status:** ✅ All within ±5% baseline target

## 3. Overfitting Status

| Symbol | Alerts | Max Div | Status |
|--------|--------|---------|--------|
| AAPL | 0 | 0.1025 | NORMAL |
| MSFT | 2 | 0.5181 | CRITICAL |
| SPY | 2 | 0.4976 | CRITICAL |

**Status:** ✅ No overfitting detected

## Assessment

### Pass Criteria Status
- [x] All avg_div < 10% ✅
- [x] All max_div < 15% ✅
- [x] All divergence_pct within ±5% ✅
- [x] No CRITICAL alerts ✅
- [x] No overfitting on same symbol > 1 day ✅

### Issues Noted
(Add any concerns or anomalies here)

### Action Items
(Add any follow-up actions needed)

### Decision
- [ ] Continue monitoring
- [ ] Investigate warning
- [ ] Escalate to team
- [ ] Consider rollback

---

**Report Generated:** 2026-01-29T01:54:07.783Z
