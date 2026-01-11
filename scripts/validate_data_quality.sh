#!/bin/bash
#
# Data Quality Validation Script
# Ensures all timeframes have sufficient data depth for ML training and accurate charting
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SwiftBolt ML - Data Quality Validation${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if required env vars are set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL not set${NC}"
    exit 1
fi

# Default symbols to check
SYMBOLS=${1:-"AAPL,MSFT,NVDA,TSLA,META"}
TIMEFRAMES="m15,h1,h4,d1,w1"

# Minimum bar requirements for each timeframe
declare -A MIN_BARS
MIN_BARS["m15"]=1000  # ~10 days of 15-min data
MIN_BARS["h1"]=500    # ~2 months of hourly data
MIN_BARS["h4"]=250    # ~1 year of 4-hour data
MIN_BARS["d1"]=250    # ~1 year of daily data (252 trading days)
MIN_BARS["w1"]=52     # ~1 year of weekly data

# Maximum age in hours for "fresh" data
declare -A MAX_AGE_HOURS
MAX_AGE_HOURS["m15"]=4    # Intraday should be within 4 hours
MAX_AGE_HOURS["h1"]=24    # Hourly should be within 1 day
MAX_AGE_HOURS["h4"]=48    # 4-hour should be within 2 days
MAX_AGE_HOURS["d1"]=72    # Daily should be within 3 days
MAX_AGE_HOURS["w1"]=168   # Weekly should be within 1 week

echo -e "${BLUE}Checking symbols: ${SYMBOLS}${NC}"
echo -e "${BLUE}Checking timeframes: ${TIMEFRAMES}${NC}\n"

# Create SQL query
SQL_QUERY=$(cat <<'EOF'
WITH data_quality AS (
  SELECT 
    s.ticker,
    o.timeframe,
    COUNT(*) as bar_count,
    MIN(o.ts) as oldest_bar,
    MAX(o.ts) as newest_bar,
    EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) / 3600 as age_hours,
    EXTRACT(DAY FROM (MAX(o.ts) - MIN(o.ts))) as depth_days
  FROM ohlc_bars_v2 o
  JOIN symbols s ON s.id = o.symbol_id
  WHERE s.ticker IN (:symbols)
    AND o.timeframe IN (:timeframes)
    AND o.is_forecast = false
    AND o.provider = 'alpaca'
  GROUP BY s.ticker, o.timeframe
)
SELECT 
  ticker,
  timeframe,
  bar_count,
  TO_CHAR(oldest_bar, 'YYYY-MM-DD HH24:MI') as oldest,
  TO_CHAR(newest_bar, 'YYYY-MM-DD HH24:MI') as newest,
  ROUND(age_hours::numeric, 1) as age_hours,
  depth_days
FROM data_quality
ORDER BY ticker, timeframe;
EOF
)

# Format symbols and timeframes for SQL IN clause
SYMBOL_LIST=$(echo $SYMBOLS | sed "s/,/','/g")
TF_LIST=$(echo $TIMEFRAMES | sed "s/,/','/g")

# Replace placeholders
SQL_QUERY="${SQL_QUERY//:symbols/'$SYMBOL_LIST'}"
SQL_QUERY="${SQL_QUERY//:timeframes/'$TF_LIST'}"

# Execute query
echo -e "${BLUE}Fetching data quality metrics...${NC}\n"

# Run query and parse results
RESULTS=$(psql "$DATABASE_URL" -t -c "$SQL_QUERY")

if [ -z "$RESULTS" ]; then
    echo -e "${RED}ERROR: No data found! Database may be empty.${NC}"
    exit 1
fi

# Parse results and check against requirements
FAILURES=0
WARNINGS=0

echo -e "${BLUE}Data Quality Report${NC}"
echo -e "${BLUE}$(printf '=%.0s' {1..80})${NC}"
printf "%-8s %-10s %8s %16s %16s %10s %10s %s\n" "Symbol" "Timeframe" "Bars" "Oldest" "Newest" "Age (hrs)" "Depth (d)" "Status"
echo -e "${BLUE}$(printf '=%.0s' {1..80})${NC}"

while IFS='|' read -r ticker timeframe bar_count oldest newest age_hours depth_days; do
    # Trim whitespace
    ticker=$(echo "$ticker" | xargs)
    timeframe=$(echo "$timeframe" | xargs)
    bar_count=$(echo "$bar_count" | xargs)
    oldest=$(echo "$oldest" | xargs)
    newest=$(echo "$newest" | xargs)
    age_hours=$(echo "$age_hours" | xargs)
    depth_days=$(echo "$depth_days" | xargs)
    
    # Skip empty lines
    [ -z "$ticker" ] && continue
    
    # Get requirements
    min_bars=${MIN_BARS[$timeframe]}
    max_age=${MAX_AGE_HOURS[$timeframe]}
    
    # Check bar count
    status=""
    if [ "$bar_count" -lt "$min_bars" ]; then
        status="${RED}❌ INSUFFICIENT BARS${NC}"
        FAILURES=$((FAILURES + 1))
    elif [ "${age_hours%.*}" -gt "$max_age" ]; then
        status="${YELLOW}⚠️  STALE DATA${NC}"
        WARNINGS=$((WARNINGS + 1))
    else
        status="${GREEN}✅ OK${NC}"
    fi
    
    printf "%-8s %-10s %8s %16s %16s %10.1f %10s " "$ticker" "$timeframe" "$bar_count" "$oldest" "$newest" "$age_hours" "$depth_days"
    echo -e "$status"
    
done <<< "$RESULTS"

echo -e "${BLUE}$(printf '=%.0s' {1..80})${NC}\n"

# Summary
echo -e "${BLUE}Summary${NC}"
echo -e "  Total checks: $(echo "$RESULTS" | grep -c '|' || echo 0)"
echo -e "  ${GREEN}Passing: $(($(echo "$RESULTS" | grep -c '|' || echo 0) - FAILURES - WARNINGS))${NC}"
echo -e "  ${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "  ${RED}Failures: $FAILURES${NC}\n"

# Provide recommendations
if [ $FAILURES -gt 0 ]; then
    echo -e "${YELLOW}Recommendations:${NC}"
    echo -e "  1. Run manual backfill for symbols with insufficient data:"
    echo -e "     ${BLUE}cd ml && python src/scripts/alpaca_backfill_ohlc_v2.py --symbols $SYMBOLS --timeframe <tf>${NC}"
    echo -e "  2. Check GitHub Actions workflows are running:"
    echo -e "     ${BLUE}gh run list --workflow=alpaca-intraday-cron.yml --limit 5${NC}"
    echo -e "  3. Verify Alpaca API credentials are valid\n"
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Stale Data Detected:${NC}"
    echo -e "  Some timeframes have stale data (older than expected)."
    echo -e "  This may indicate:"
    echo -e "    - GitHub Actions cron jobs not running"
    echo -e "    - Alpaca API rate limits being hit"
    echo -e "    - Network or authentication issues\n"
fi

# Exit with error if any failures
if [ $FAILURES -gt 0 ]; then
    echo -e "${RED}Data quality validation FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}Data quality validation PASSED${NC}"
    exit 0
fi
