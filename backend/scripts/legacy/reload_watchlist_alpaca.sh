#!/bin/bash
# ============================================================================
# Reload Watchlist Chart Data with Alpaca
# ============================================================================
# Purpose: Clear legacy data and reload with Alpaca-only provider
# Date: 2026-01-10
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "Watchlist Chart Data Reload - Alpaca Migration"
echo "============================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Clear existing data
echo -e "${YELLOW}Step 1: Clearing legacy chart data for watchlist symbols...${NC}"
echo "Symbols: AAPL, AMD, AMZN, CRWD, MU, NVDA, PLTR"
echo ""

# Check if we're in the right directory
if [ ! -f "backend/scripts/clear_watchlist_chart_data.sql" ]; then
    echo -e "${RED}Error: Must run from SwiftBolt_ML root directory${NC}"
    exit 1
fi

# Run cleanup SQL via psql
echo "Executing cleanup script..."
if command -v psql &> /dev/null; then
    # Use direct psql connection
    psql "$DATABASE_URL" -f backend/scripts/clear_watchlist_chart_data.sql
elif [ -f ".env" ]; then
    # Try to extract connection string from .env
    source .env
    psql "$DATABASE_URL" -f backend/scripts/clear_watchlist_chart_data.sql
else
    echo -e "${RED}Error: psql not found and no DATABASE_URL in .env${NC}"
    echo "Please run the SQL manually:"
    echo "  cat backend/scripts/clear_watchlist_chart_data.sql | psql \$DATABASE_URL"
    exit 1
fi

echo -e "${GREEN}✓ Data cleared successfully${NC}"
echo ""

# Step 2: Backfill hourly data
echo -e "${YELLOW}Step 2: Backfilling hourly (h1) data with Alpaca...${NC}"
echo "This will fetch ~100 bars per symbol for chart display"
echo ""

cd ml
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1

echo -e "${GREEN}✓ Hourly data backfilled${NC}"
echo ""

# Step 3: Backfill daily data
echo -e "${YELLOW}Step 3: Backfilling daily (d1) data with Alpaca...${NC}"
echo "This provides longer-term historical context"
echo ""

python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe d1

echo -e "${GREEN}✓ Daily data backfilled${NC}"
echo ""

# Step 4: Verify data
echo -e "${YELLOW}Step 4: Verifying data integrity...${NC}"
cd ..

# Run verification query
if command -v psql &> /dev/null; then
    psql "$DATABASE_URL" <<SQL
SELECT 
  s.ticker,
  ob.provider,
  ob.timeframe,
  COUNT(*) as bar_count,
  MAX(ob.ts) as latest_bar
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'alpaca'
GROUP BY s.ticker, ob.provider, ob.timeframe
ORDER BY s.ticker, ob.timeframe;
SQL
else
    echo -e "${YELLOW}Skipping verification (psql not available)${NC}"
fi

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}✓ Watchlist chart data reload complete!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo "Next steps:"
echo "1. Open SwiftBoltML macOS app"
echo "2. Load any watchlist symbol (AAPL, NVDA, etc.)"
echo "3. Verify chart shows 100 bars on initial load"
echo "4. Check that provider shows 'alpaca' in chart metadata"
echo "5. Test pan/zoom controls work correctly"
echo ""
echo "Chart standards:"
echo "- Default zoom: 100 bars"
echo "- Bar spacing: 12px"
echo "- Right offset: 30px"
echo "- Provider: alpaca (only)"
echo ""
