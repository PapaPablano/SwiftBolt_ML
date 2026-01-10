#!/bin/bash
# ============================================================================
# Backfill All Timeframes for Watchlist Symbols
# ============================================================================
# Purpose: Ensure complete data coverage across all timeframes
# Timeframes: 15m, 1h, 4h, 1d, 1w
# Date: 2026-01-10
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "Backfilling All Timeframes - Alpaca Data"
echo "============================================================================"
echo ""
echo "Timeframes: 15m (15-minute), 1h (hourly), 4h (4-hour), 1d (daily), 1w (weekly)"
echo "Symbols: All watchlist symbols (AAPL, AMD, AMZN, CRWD, MU, NVDA, PLTR, etc.)"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Timeframes to backfill
TIMEFRAMES=("m15" "h1" "h4" "d1" "w1")

# Track progress
TOTAL_TIMEFRAMES=${#TIMEFRAMES[@]}
CURRENT=0

for timeframe in "${TIMEFRAMES[@]}"; do
    CURRENT=$((CURRENT + 1))
    
    echo -e "${YELLOW}[$CURRENT/$TOTAL_TIMEFRAMES] Backfilling $timeframe timeframe...${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Run backfill for this timeframe
    python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe "$timeframe"
    
    echo -e "${GREEN}✓ $timeframe complete${NC}"
    echo ""
    
    # Small delay between timeframes to avoid rate limits
    if [ $CURRENT -lt $TOTAL_TIMEFRAMES ]; then
        echo "Waiting 2 seconds before next timeframe..."
        sleep 2
    fi
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}✓ All timeframes backfilled successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo "Summary:"
echo "  ✓ 15-minute bars (m15) - Intraday trading"
echo "  ✓ 1-hour bars (h1) - Short-term analysis"
echo "  ✓ 4-hour bars (h4) - Swing trading"
echo "  ✓ Daily bars (d1) - Position trading"
echo "  ✓ Weekly bars (w1) - Long-term trends"
echo ""
echo "Next steps:"
echo "1. Verify data in Supabase dashboard"
echo "2. Test charts in macOS app (should show 100 bars by default)"
echo "3. Switch between timeframes to verify all load correctly"
echo ""
