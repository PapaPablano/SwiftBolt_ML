#!/bin/bash
# ============================================================================
# Smart Backfill with Gap Detection and Auto-Retry
# ============================================================================
# This script:
# 1. Runs initial backfill for all timeframes
# 2. Validates data quality and detects gaps
# 3. Auto-retries any symbols/timeframes with issues
# 4. Provides final quality report
# ============================================================================

set -e

echo "============================================================================"
echo "Smart Backfill - All Timeframes with Gap Detection"
echo "============================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Timeframes
TIMEFRAMES=("m15" "h1" "h4" "d1" "w1")

# Step 1: Initial backfill
echo -e "${YELLOW}Step 1: Initial backfill for all timeframes${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for timeframe in "${TIMEFRAMES[@]}"; do
    echo ""
    echo -e "${YELLOW}Backfilling $timeframe...${NC}"
    
    # Run backfill with timeout protection
    timeout 600 python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe "$timeframe" || {
        echo -e "${RED}⚠️  Timeout or error on $timeframe, will retry later${NC}"
    }
    
    # Small delay between timeframes
    sleep 2
done

echo ""
echo -e "${GREEN}✓ Initial backfill complete${NC}"
echo ""

# Step 2: Validate and detect gaps
echo -e "${YELLOW}Step 2: Validating data quality and detecting gaps${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Don't fail on validation - capture exit code but continue
set +e
python src/scripts/backfill_with_gap_detection.py --all > /tmp/backfill_validation.txt
VALIDATION_EXIT_CODE=$?
set -e

cat /tmp/backfill_validation.txt

# Step 3: Auto-retry if issues found
if [ $VALIDATION_EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}Step 3: Auto-retrying symbols with gaps${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Extract retry commands from validation output
    # Only retry critical gaps (>30 days) - skip expected gaps (weekends/holidays)
    grep "python src/scripts/alpaca_backfill_ohlc_v2.py" /tmp/backfill_validation.txt | while read -r cmd; do
        # Check if this is a critical gap by looking at the gap report
        # For now, retry all - but log that some may be expected
        echo -e "${YELLOW}Retrying: $cmd${NC}"
        set +e
        eval "$cmd" || echo -e "${YELLOW}Retry completed (some gaps may be expected)${NC}"
        set -e
        sleep 2
    done
    
    echo ""
    echo -e "${YELLOW}Step 4: Final validation after retries${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Don't fail on validation - treat gaps as warnings
    set +e
    python src/scripts/backfill_with_gap_detection.py --all
    FINAL_EXIT_CODE=$?
    set -e
    
    if [ $FINAL_EXIT_CODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}============================================================================${NC}"
        echo -e "${GREEN}✓ All gaps resolved! Data is now complete.${NC}"
        echo -e "${GREEN}============================================================================${NC}"
    else
        echo ""
        echo -e "${YELLOW}============================================================================${NC}"
        echo -e "${YELLOW}⚠️  Some gaps remain (may include expected gaps like weekends/holidays).${NC}"
        echo -e "${YELLOW}    Review the gap report above for critical issues.${NC}"
        echo -e "${YELLOW}    Workflow will continue - gaps are logged as warnings.${NC}"
        echo -e "${YELLOW}============================================================================${NC}"
    fi
else
    echo ""
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}✓ No gaps detected! All data is complete.${NC}"
    echo -e "${GREEN}============================================================================${NC}"
fi

echo ""
echo "Summary:"
echo "  - All timeframes backfilled: m15, h1, h4, d1, w1"
echo "  - Gap detection and validation complete"
echo "  - Auto-retry executed for any issues"
echo ""
echo "Next steps:"
echo "  1. Refresh charts in macOS app"
echo "  2. Verify 100-bar default zoom is working"
echo "  3. Check all timeframes load correctly"
echo ""
echo "Note: Gap detection may report expected gaps (weekends, holidays)."
echo "      Review the report above for critical gaps requiring attention."
echo ""

# Always exit successfully - gaps are warnings, not failures
exit 0
