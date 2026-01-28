#!/bin/bash

##############################################################################
# Phase 7.1 Canary Daily Monitoring Script
# Run once daily at 6 PM to generate complete daily report
# Usage: bash scripts/canary_daily_monitoring.sh
##############################################################################

set -e

# Configuration
REPORT_DIR="canary_monitoring_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/$(date +%Y%m%d)_canary_report.md"

# Ensure report directory exists
mkdir -p "${REPORT_DIR}"

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Phase 7.1 Canary Daily Monitoring Report             ║${NC}"
echo -e "${BLUE}║  Generated: $(date '+%Y-%m-%d %H:%M:%S')                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Start report file
cat > "${REPORT_FILE}" << 'HEADER'
# Phase 7.1 Canary Daily Monitoring Report

HEADER

echo "Date: $(date '+%Y-%m-%d')" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

# ============================================================================
# QUERY 1: Daily Divergence Summary
# ============================================================================
echo -e "${BLUE}[1/3] Running Divergence Summary Query...${NC}"

DIVERGENCE_QUERY=$(cat <<'SQL'
SELECT
  symbol,
  COUNT(*) as windows,
  ROUND(AVG(divergence)::numeric, 4) as avg_div,
  ROUND(MAX(divergence)::numeric, 4) as max_div,
  ROUND(MIN(divergence)::numeric, 4) as min_div,
  COUNT(CASE WHEN is_overfitting THEN 1 END) as overfitting_alerts
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY')
  AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol
ORDER BY max_div DESC;
SQL
)

cat >> "${REPORT_FILE}" << 'SECTION1'
## 1. Divergence Summary

| Metric | AAPL | MSFT | SPY |
|--------|------|------|-----|
SECTION1

DIVERGENCE_RESULTS=$(psql "${DATABASE_URL}" -t -c "${DIVERGENCE_QUERY}")

echo "" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "${DIVERGENCE_RESULTS}" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

echo -e "${GREEN}✓ Divergence Summary Complete${NC}"

# ============================================================================
# QUERY 2: RMSE vs Baseline
# ============================================================================
echo -e "${BLUE}[2/3] Running RMSE Comparison Query...${NC}"

RMSE_QUERY=$(cat <<'SQL'
SELECT
  symbol,
  ROUND(AVG(val_rmse)::numeric, 4) as avg_val_rmse,
  ROUND(AVG(test_rmse)::numeric, 4) as avg_test_rmse,
  ROUND(100 * (AVG(test_rmse) - AVG(val_rmse)) / AVG(val_rmse), 2) as divergence_pct,
  COUNT(*) as samples
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY')
  AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol
ORDER BY divergence_pct DESC;
SQL
)

cat >> "${REPORT_FILE}" << 'SECTION2'

## 2. RMSE vs Baseline

| Symbol | Val RMSE | Test RMSE | Divergence % | Samples |
|--------|----------|-----------|--------------|---------|
SECTION2

RMSE_RESULTS=$(psql "${DATABASE_URL}" -t -c "${RMSE_QUERY}")

echo "" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "${RMSE_RESULTS}" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

echo -e "${GREEN}✓ RMSE Comparison Complete${NC}"

# ============================================================================
# QUERY 3: Overfitting Status
# ============================================================================
echo -e "${BLUE}[3/3] Running Overfitting Status Query...${NC}"

OVERFITTING_QUERY=$(cat <<'SQL'
SELECT
  symbol,
  COUNT(CASE WHEN is_overfitting THEN 1 END) as alert_count,
  MAX(divergence) as max_divergence,
  CASE
    WHEN MAX(divergence) > 0.30 THEN 'CRITICAL'
    WHEN MAX(divergence) > 0.20 THEN 'WARNING'
    WHEN MAX(divergence) > 0.15 THEN 'ELEVATED'
    ELSE 'NORMAL'
  END as status
FROM ensemble_validation_metrics
WHERE symbol IN ('AAPL', 'MSFT', 'SPY')
  AND DATE(validation_date) = CURRENT_DATE
GROUP BY symbol
ORDER BY max_divergence DESC;
SQL
)

cat >> "${REPORT_FILE}" << 'SECTION3'

## 3. Overfitting Status

| Symbol | Alerts | Max Div | Status |
|--------|--------|---------|--------|
SECTION3

OVERFITTING_RESULTS=$(psql "${DATABASE_URL}" -t -c "${OVERFITTING_QUERY}")

echo "" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "${OVERFITTING_RESULTS}" >> "${REPORT_FILE}"
echo "\`\`\`" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

echo -e "${GREEN}✓ Overfitting Status Complete${NC}"

# ============================================================================
# Assessment & Decision
# ============================================================================
cat >> "${REPORT_FILE}" << 'ASSESSMENT'

## Assessment

### Pass Criteria
- [ ] All avg_div < 10%
- [ ] All max_div < 15%
- [ ] All divergence_pct within ±5%
- [ ] No CRITICAL alerts
- [ ] No overfitting on same symbol > 1 day

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

**Report Generated:**
ASSESSMENT

echo "$(date '+%Y-%m-%d %H:%M:%S')" >> "${REPORT_FILE}"

echo "" >> "${REPORT_FILE}"

# ============================================================================
# Output Summary to Terminal
# ============================================================================
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}DAILY MONITORING SUMMARY${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Divergence Summary:"
echo "${DIVERGENCE_RESULTS}" | column -t
echo ""
echo "RMSE Comparison:"
echo "${RMSE_RESULTS}" | column -t
echo ""
echo "Overfitting Status:"
echo "${OVERFITTING_RESULTS}" | column -t
echo ""
echo -e "${GREEN}✓ Report generated: ${REPORT_FILE}${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review report: less ${REPORT_FILE}"
echo "  2. Check if all metrics are PASS"
echo "  3. Edit assessment section with notes"
echo "  4. Commit report to git if desired"
echo ""
