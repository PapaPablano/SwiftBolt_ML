# Phase 7.1 Canary - 6 Trading Day Monitoring Checklist

## Quick Reference - Print This!

```
Period: January 28 - February 4, 2026
(6 trading days: Wed-Fri, Mon-Wed)
Time: 6 PM every market day (~5 minutes)
```

---

## Daily Check (1 Minute Per Day)

### ✅ Every Day at 6 PM

```bash
bash scripts/canary_daily_monitoring.sh
```

### ✅ Read the Report

```bash
cat canary_monitoring_reports/$(date +%Y%m%d)_canary_report.md
```

### ✅ Check These Numbers:
- [ ] All `avg_div` < **10%**
- [ ] All `max_div` < **15%**
- [ ] All `divergence_pct` ±**5%**
- [ ] `overfitting_alerts` = **0**
- [ ] Status = **NORMAL** (not CRITICAL)

### ✅ If All Pass: Continue monitoring next day
### ⚠️ If Any Warning: Add notes and monitor closely
### 🚨 If Critical: Alert team, consider rollback

---

## Day-by-Day Checklist (6 Trading Days)

### 📅 Trading Day 1: January 28 (Wed)
- [ ] 6 PM: Run `bash scripts/canary_daily_monitoring.sh`
- [ ] Review metrics
- [ ] All green? ✅ Continue

**Report:** `canary_monitoring_reports/20260128_canary_report.md`

### 📅 Trading Day 2: January 29 (Thu)
- [ ] 6 PM: Run monitoring script
- [ ] Review metrics
- [ ] All green? ✅ Continue

**Report:** `canary_monitoring_reports/20260129_canary_report.md`

### 📅 Trading Day 3: January 30 (Fri)
- [ ] 6 PM: Run monitoring script
- [ ] Review metrics
- [ ] All green? ✅ Continue

**Report:** `canary_monitoring_reports/20260130_canary_report.md`

### 📅 WEEKEND (Jan 31 - Feb 1)
- [ ] No monitoring (market closed)
- [ ] No new data generated
- [ ] Resume Monday

### 📅 Trading Day 4: February 2 (Mon)
- [ ] 6 PM: Run monitoring script
- [ ] Review metrics
- [ ] All green? ✅ Continue

**Report:** `canary_monitoring_reports/20260202_canary_report.md`

### 📅 Trading Day 5: February 3 (Tue)
- [ ] 6 PM: Run monitoring script
- [ ] Review metrics
- [ ] All green? ✅ Continue

**Report:** `canary_monitoring_reports/20260203_canary_report.md`

### 📅 Trading Day 6: February 4 (Wed) - FINAL DAY
- [ ] 6 PM: Run monitoring script
- [ ] Review all 6 trading days of reports
- [ ] Make PASS/FAIL decision
- [ ] Document final decision

**Report:** `canary_monitoring_reports/20260204_canary_report.md`

---

## Success Criteria

### ✅ PASS (Proceed to Phase 7.2)
```
✓ All 7 days: avg_div < 10%
✓ All 7 days: max_div < 15%
✓ All 7 days: divergence_pct within ±5%
✓ Total critical alerts: 0
✓ No system errors
```

### ❌ FAIL (Execute Rollback)
```
✗ Any day: avg_div > 15%
✗ Any day: max_div > 20-30%
✗ Any day: divergence_pct > ±10%
✗ Critical alerts > 2
✗ System errors or crashes
```

---

## Command Reference

### Run Monitoring (Only command you need!)
```bash
bash scripts/canary_daily_monitoring.sh
```

### View Today's Report
```bash
cat canary_monitoring_reports/$(date +%Y%m%d)_canary_report.md
```

### View All Reports
```bash
ls -lh canary_monitoring_reports/
```

### Emergency Rollback (If needed)
```bash
bash scripts/rollback_to_legacy.sh
```

---

## What Numbers Mean

### Divergence (Most Important)
| Value | Status | Action |
|-------|--------|--------|
| < 10% | ✅ Good | Continue |
| 10-15% | ⚠️ Warning | Monitor |
| 15-20% | 🟡 Elevated | Alert team |
| > 20-30% | 🔴 Critical | Rollback |

### RMSE vs Baseline
| Value | Status | Action |
|-------|--------|--------|
| ±0-3% | ✅ Excellent | Continue |
| ±3-5% | ✅ Good | Continue |
| ±5-8% | ⚠️ Warning | Monitor |
| > ±10% | 🔴 Critical | Rollback |

### Overfitting Alerts
| Count | Status | Action |
|-------|--------|--------|
| 0 | ✅ Perfect | Continue |
| 1 | ✅ Acceptable | Monitor |
| 2+ | ⚠️ Warning | Alert |
| > 3 consecutive | 🔴 Critical | Rollback |

---

## Email Summary Template

**Use this to update team daily:**

```
Subject: Phase 7.1 Canary - Day N Report

Status: ✅ PASS / ⚠️ WARNING / 🔴 CRITICAL

Divergence:
  • AAPL: 8.1% (target: < 10%)
  • MSFT: 6.2% (target: < 10%)
  • SPY:  7.7% (target: < 10%)

RMSE vs Baseline:
  • AAPL: +2.3% (target: ±5%)
  • MSFT: -1.5% (target: ±5%)
  • SPY:  +3.1% (target: ±5%)

Alerts: 0 critical (target: 0)

Decision: Continue monitoring → Day N+1

Full Report: canary_monitoring_reports/20260128_canary_report.md
```

---

## Final Day 7 Decision

### After reviewing all 7 reports, decide:

- [ ] **PASS** - All metrics green, proceed to Phase 7.2
  - Document: "Canary successful - Phase 7.2 approved"
  - Next: Schedule Phase 7.2 limited rollout

- [ ] **MARGINAL** - Some warnings but trending good
  - Document: "Canary marginal - Team review needed"
  - Next: Team meeting to discuss

- [ ] **FAIL** - Critical issues or downward trend
  - Document: "Canary failed - Rollback executed"
  - Command: `bash scripts/rollback_to_legacy.sh`
  - Next: Post-mortem analysis

---

## Help Needed?

### Canary Monitoring
See: `CANARY_DAILY_MONITORING_PROCEDURE.md`

### Understanding Metrics
See: `PHASE_7_PRODUCTION_ROLLOUT.md` (pages 5-6)

### Emergency Rollback
See: `scripts/rollback_to_legacy.sh` (automated - just run it)

### Full Documentation
See: `PHASE_7_CANARY_EXECUTION_PLAN.md`

---

## Notes

**Jan 28-Feb 3:** Daily 6 PM check

**5 minutes per day**

**35 minutes total**

**→ Data-driven decision at end**

---

**You've got this! 🚀**

```
Phase 7.1 Canary: AAPL, MSFT, SPY (1D)
Expected RMSE Improvement: 15-30%
```
