#!/bin/bash
# Backfill missing data from June 2025 to today
# This script calls chart-data-v2 with reloadIgnoringLocalCacheData to force fresh Alpaca fetches

set -e

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

# Watchlist symbols (from logs)
SYMBOLS=("AAPL" "NVDA" "CRWD" "AMD" "PLTR" "MU" "TSLA" "GOOG")

# All timeframes per multi-timeframe rule
TIMEFRAMES=("m15" "h1" "h4" "d1" "w1")

echo "========================================="
echo "Backfilling Missing Data"
echo "From: June 2025 to Today (Jan 2026)"
echo "========================================="
echo ""

for symbol in "${SYMBOLS[@]}"; do
  echo "Processing $symbol..."
  
  for timeframe in "${TIMEFRAMES[@]}"; do
    echo "  Fetching $timeframe data..."
    
    # Determine days parameter based on timeframe
    if [ "$timeframe" = "d1" ] || [ "$timeframe" = "w1" ]; then
      DAYS=730  # 2 years for daily/weekly
    else
      DAYS=60   # 60 days for intraday
    fi
    
    # Call chart-data-v2 to trigger fresh Alpaca fetch
    RESPONSE=$(curl -s -X POST \
      "$SUPABASE_URL/functions/v1/chart-data-v2" \
      -H "Authorization: Bearer $ANON_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"symbol\": \"$symbol\",
        \"timeframe\": \"$timeframe\",
        \"days\": $DAYS,
        \"includeForecast\": true,
        \"forecastDays\": 10
      }")
    
    # Check if successful
    if echo "$RESPONSE" | grep -q '"symbol"'; then
      # Extract bar count
      HIST_COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | head -1 | grep -o '[0-9]*')
      echo "    ✓ Loaded $HIST_COUNT bars for $timeframe"
    else
      echo "    ✗ Failed to load $timeframe"
      echo "    Response: $RESPONSE"
    fi
    
    # Small delay to avoid rate limiting
    sleep 0.5
  done
  
  echo ""
done

echo "========================================="
echo "Backfill Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Run check_data_freshness.sql to verify data"
echo "2. Clear app cache and reload charts"
echo ""
