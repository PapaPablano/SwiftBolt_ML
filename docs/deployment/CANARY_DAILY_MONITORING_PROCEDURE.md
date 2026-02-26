# Phase 7.1 Canary Daily Monitoring Procedure

**Period:** January 28 - February 4, 2026 (6 trading days)
**Frequency:** Once per market day at 6 PM
**Duration:** ~5 minutes per day
**Total Time:** ~30 minutes over 6 trading days
**Note:** Weekends (Jan 31 - Feb 1) have no market data, monitoring resumes Monday Feb 2

---

## Quick Start

### Option 1: Manual (Recommended - Simplest)

**Every day at 6 PM (Jan 28 - Feb 3):**

```bash
cd /Users/ericpeterson/SwiftBolt_ML
bash scripts/canary_daily_monitoring.sh
```

Done! ✅ Report generated automatically.

---

### Option 2: Automated (Cron)

**Set up once, runs automatically:**

```bash
# Open crontab editor
crontab -e

# Add this line (runs every day at 6 PM):
0 18 * * * cd /Users/ericpeterson/SwiftBolt_ML && bash scripts/canary_daily_monitoring.sh >> canary_monitoring_reports/cron.log 2>&1

# Save and exit
```

Then just check the report each day.

---

## Daily Checklist (6 PM)

### Step 1: Generate Report (1 minute)
```bash
bash scripts/canary_daily_monitoring.sh
```

Expected output:
```
✓ Divergence Summary Complete
✓ RMSE Comparison Complete
✓ Overfitting Status Complete
✓ Report generated: canary_monitoring_reports/20260128_canary_report.md
```

### Step 2: Review Report (2 minutes)
```bash
cat canary_monitoring_reports/$(date +%Y%m%d)_canary_report.md
```

Look for:
- [ ] All `avg_div` < 10% ✅
- [ ] All `max_div` < 15% ✅
- [ ] All `divergence_pct` within ±5% ✅
- [ ] No CRITICAL alerts ✅
- [ ] No overfitting_alerts > 1 ✅

### Step 3: Edit Assessment Section (2 minutes)
```bash
nano canary_monitoring_reports/$(date +%Y%m%d)_canary_report.md
```

Add notes in the Assessment section:
- Any metrics that concern you
- Any alerts or anomalies
- What action you're taking

Example:
```markdown
### Issues Noted
- SPY divergence slightly elevated at 14.2% (near threshold)
- All other metrics normal

### Action Items
- Monitor SPY closely tomorrow
- Check if divergence trending up or stable

### Decision
- [x] Continue monitoring
- [ ] Investigate warning
- [ ] Escalate to team
- [ ] Consider rollback
```

### Step 4: Commit Report (Optional, 1 minute)
```bash
git add canary_monitoring_reports/$(date +%Y%m%d)_canary_report.md
git commit -m "Day N Canary Report: $(date +%Y-%m-%d) - All metrics passing"
```

---

## Daily Status Summary (To Share With Team)

After each report, you can quickly summarize for the team:

```
Date: Jan 28, 2026 - Day 1

✅ PASS CRITERIA MET
  • Divergence: AAPL 8.1%, MSFT 6.2%, SPY 7.7% (all < 10% ✓)
  • RMSE: All within ±5% baseline (✓)
  • Alerts: 0 critical alerts (✓)
  • Status: NORMAL

📊 Full Report: canary_monitoring_reports/20260128_canary_report.md

→ Ready for Day 2
```

---

## What To Watch For

### 🟢 GREEN - Everything Good
```
Avg Divergence: < 10%
Max Divergence: < 15%
Divergence %:   ±3-5%
Alerts:         0
Status:         NORMAL
```
→ **Action:** Continue monitoring, no changes needed

### 🟡 YELLOW - Warning Zone
```
Avg Divergence: 10-15%
Max Divergence: 15-20%
Divergence %:   ±5-8%
Alerts:         1-2
Status:         ELEVATED
```
→ **Action:** Monitor closely, investigate cause, consider alert

### 🔴 RED - Critical
```
Avg Divergence: > 15%
Max Divergence: > 20-30%
Divergence %:   > ±10%
Alerts:         > 2
Status:         CRITICAL
```
→ **Action:** Alert team immediately, consider rollback

---

## Decision Framework (Day 7)

### If All 7 Days = GREEN ✅
```
DECISION: PASS → Proceed to Phase 7.2
```

### If Any Day = YELLOW ⚠️
```
DECISION: Review with team
  • If isolated and recovers → PASS
  • If persistent trend → FAIL
```

### If Any Day = RED 🔴
```
DECISION: FAIL → Execute Rollback
  bash scripts/rollback_to_legacy.sh
```

---

## Reference Queries

If you need to run individual queries (optional):

### Divergence Only
```bash
psql "${DATABASE_URL}" << 'SQL'
SELECT symbol, COUNT(*) as windows, ROUND(AVG(divergence)::numeric, 4) as avg_div,
  ROUND(MAX(divergence)::numeric, 4) as max_div, COUNT(CASE WHEN is_overfitting THEN 1 END) as alerts
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY') AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol ORDER BY max_div DESC;
SQL
```

### RMSE Only
```bash
psql "${DATABASE_URL}" << 'SQL'
SELECT symbol, ROUND(AVG(val_rmse)::numeric, 4) as val_rmse, ROUND(AVG(test_rmse)::numeric, 4) as test_rmse,
  ROUND(100 * (AVG(test_rmse) - AVG(val_rmse)) / AVG(val_rmse), 2) as divergence_pct, COUNT(*) as samples
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY') AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol ORDER BY divergence_pct DESC;
SQL
```

### Overfitting Status Only
```bash
psql "${DATABASE_URL}" << 'SQL'
SELECT symbol, COUNT(CASE WHEN is_overfitting THEN 1 END) as alerts,
  MAX(divergence) as max_div,
  CASE WHEN MAX(divergence) > 0.30 THEN 'CRITICAL' WHEN MAX(divergence) > 0.20 THEN 'WARNING'
    WHEN MAX(divergence) > 0.15 THEN 'ELEVATED' ELSE 'NORMAL' END as status
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY') AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol ORDER BY max_div DESC;
SQL
```

---

## Files Generated

```
canary_monitoring_reports/
├── 20260128_canary_report.md   (Day 1)
├── 20260129_canary_report.md   (Day 2)
├── 20260130_canary_report.md   (Day 3)
├── 20260131_canary_report.md   (Day 4)
├── 20260201_canary_report.md   (Day 5)
├── 20260202_canary_report.md   (Day 6)
├── 20260203_canary_report.md   (Day 7 - FINAL DECISION)
└── cron.log                    (if using automated cron)
```

---

## Timeline

| Date | Day | Action | Status |
|------|-----|--------|--------|
| Jan 27 | Setup | Run canary deployment script | Complete ✅ |
| Jan 28 | Day 1 | 6 PM: Generate first report | Pending ⏳ |
| Jan 29 | Day 2 | 6 PM: Review & update | Pending ⏳ |
| Jan 30 | Day 3 | 6 PM: Review & update | Pending ⏳ |
| Jan 31 | Day 4 | 6 PM: Review & update | Pending ⏳ |
| Feb 1 | Day 5 | 6 PM: Review & update | Pending ⏳ |
| Feb 2 | Day 6 | 6 PM: Review & update | Pending ⏳ |
| Feb 3 | Day 7 | 6 PM: Final report & decision | Pending ⏳ |
| Feb 4 | Decision | Pass/Fail determination | Pending ⏳ |

---

## Troubleshooting

### Script Fails with Database Connection Error
```
Error: could not translate host name "..."

Solution: Set DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
bash scripts/canary_daily_monitoring.sh
```

### Report Directory Permission Error
```
mkdir: cannot create directory 'canary_monitoring_reports'

Solution: Create directory manually
mkdir -p canary_monitoring_reports
chmod 755 canary_monitoring_reports
```

### Script Takes Too Long
```
Normal: 5-10 seconds
Too Long (> 1 minute): Check database performance

Solution: Run individual queries to identify slow one
```

---

## Summary

**Daily Time Commitment:** 5 minutes at 6 PM
**Required Actions:**
1. Run script
2. Review report
3. Edit assessment notes
4. (Optional) Commit to git

**Total for 7 Days:** ~35 minutes
**Result:** Complete data-driven pass/fail decision

---

**Ready to monitor Phase 7.1 Canary!**

```bash
# Start on Jan 28 at 6 PM:
bash scripts/canary_daily_monitoring.sh
```
