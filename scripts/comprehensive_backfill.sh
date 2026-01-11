#!/bin/bash
#
# Comprehensive Multi-Timeframe Backfill Script
# Ensures all timeframes have sufficient historical data depth for ML training
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}SwiftBolt ML - Comprehensive Data Backfill${NC}"
echo -e "${BLUE}=================================================${NC}\n"

# Navigate to ml directory
cd "$(dirname "$0")/../ml"

# Load environment
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Configuration
SYMBOLS=${1:-"AAPL,MSFT,NVDA,TSLA,META,GOOGL,AMZN,SPY,QQQ,CRWD"}
FORCE_REFRESH=${2:-false}

# Timeframe configuration (timeframe:days_back)
declare -A TIMEFRAME_DAYS
TIMEFRAME_DAYS["m15"]=60      # 60 days of 15-min data
TIMEFRAME_DAYS["h1"]=180      # 6 months of hourly data
TIMEFRAME_DAYS["h4"]=365      # 1 year of 4-hour data
TIMEFRAME_DAYS["d1"]=730      # 2 years of daily data (for ML training)
TIMEFRAME_DAYS["w1"]=1460     # 4 years of weekly data

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Symbols: ${SYMBOLS}"
echo -e "  Force Refresh: ${FORCE_REFRESH}"
echo -e "  Timeframes:"
for tf in "${!TIMEFRAME_DAYS[@]}"; do
    echo -e "    - ${tf}: ${TIMEFRAME_DAYS[$tf]} days back"
done
echo ""

# Convert symbols to array
IFS=',' read -ra SYMBOL_ARRAY <<< "$SYMBOLS"

# Track results
TOTAL_SYMBOLS=${#SYMBOL_ARRAY[@]}
TOTAL_TIMEFRAMES=${#TIMEFRAME_DAYS[@]}
TOTAL_JOBS=$((TOTAL_SYMBOLS * TOTAL_TIMEFRAMES))
COMPLETED=0
FAILED=0
SKIPPED=0

echo -e "${BLUE}Starting backfill for ${TOTAL_SYMBOLS} symbols x ${TOTAL_TIMEFRAMES} timeframes = ${TOTAL_JOBS} jobs${NC}\n"

# Create results file
RESULTS_FILE="/tmp/backfill_results_$(date +%Y%m%d_%H%M%S).log"
echo "Backfill Results - $(date)" > "$RESULTS_FILE"
echo "================================" >> "$RESULTS_FILE"

# Process each symbol and timeframe
for symbol in "${SYMBOL_ARRAY[@]}"; do
    symbol=$(echo "$symbol" | xargs)  # Trim whitespace
    
    echo -e "${GREEN}Processing ${symbol}...${NC}"
    
    for timeframe in "${!TIMEFRAME_DAYS[@]}"; do
        days_back=${TIMEFRAME_DAYS[$timeframe]}
        
        echo -e "  ${BLUE}├─ ${timeframe} (${days_back} days)${NC}"
        
        # Build command
        cmd="python src/scripts/alpaca_backfill_ohlc_v2.py --symbol $symbol --timeframe $timeframe"
        
        if [ "$FORCE_REFRESH" = "true" ]; then
            cmd="$cmd --force"
        fi
        
        # Execute backfill
        if output=$($cmd 2>&1); then
            # Extract bar count from output
            bars=$(echo "$output" | grep -oP 'Persisted \K\d+' | tail -1 || echo "0")
            bars=${bars:-0}
            
            if [ "$bars" -eq "0" ]; then
                echo -e "  ${YELLOW}  └─ ⏭️  Skipped (no new data)${NC}"
                SKIPPED=$((SKIPPED + 1))
                echo "[$symbol/$timeframe] SKIPPED (no new data)" >> "$RESULTS_FILE"
            else
                echo -e "  ${GREEN}  └─ ✅ Success: $bars bars${NC}"
                COMPLETED=$((COMPLETED + 1))
                echo "[$symbol/$timeframe] SUCCESS: $bars bars" >> "$RESULTS_FILE"
            fi
        else
            echo -e "  ${RED}  └─ ❌ Failed${NC}"
            echo "$output" | head -3
            FAILED=$((FAILED + 1))
            echo "[$symbol/$timeframe] FAILED: $output" >> "$RESULTS_FILE"
        fi
        
        # Rate limiting - be nice to Alpaca API
        sleep 0.5
    done
    
    echo ""
done

# Summary
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}Backfill Complete${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "  Total Jobs: ${TOTAL_JOBS}"
echo -e "  ${GREEN}Completed: ${COMPLETED}${NC}"
echo -e "  ${YELLOW}Skipped: ${SKIPPED}${NC}"
echo -e "  ${RED}Failed: ${FAILED}${NC}"
echo -e ""
echo -e "Results saved to: ${RESULTS_FILE}"
echo ""

# Data quality check
echo -e "${BLUE}Running data quality validation...${NC}\n"
if command -v ../scripts/validate_data_quality.sh &> /dev/null; then
    ../scripts/validate_data_quality.sh "$SYMBOLS" || true
fi

# Recommendations
if [ $FAILED -gt 0 ]; then
    echo -e "${YELLOW}Some backfills failed. Check the following:${NC}"
    echo -e "  1. Alpaca API credentials: echo \$ALPACA_API_KEY"
    echo -e "  2. Database connectivity: psql \$DATABASE_URL -c 'SELECT 1'"
    echo -e "  3. Symbol validity: Check if symbols exist in Alpaca"
    echo ""
    exit 1
fi

if [ $COMPLETED -eq 0 ] && [ $SKIPPED -eq $TOTAL_JOBS ]; then
    echo -e "${GREEN}All data is up-to-date. No backfill needed.${NC}"
elif [ $COMPLETED -gt 0 ]; then
    echo -e "${GREEN}Successfully backfilled ${COMPLETED} symbol/timeframe combinations.${NC}"
    echo -e "${YELLOW}Consider triggering ML forecast updates for symbols with new data.${NC}"
fi

exit 0
