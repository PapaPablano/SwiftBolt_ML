#!/bin/bash
# Show which dates have Alpaca bars

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "Alpaca bars for AAPL h1 (showing dates):"
curl -s "${SUPABASE_URL}/rest/v1/ohlc_bars_v2?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1&provider=eq.alpaca&is_forecast=eq.false&select=ts&order=ts.desc&limit=10" \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" | jq '.[].ts'

echo ""
echo "Total Alpaca bars:"
curl -s "${SUPABASE_URL}/rest/v1/ohlc_bars_v2?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1&provider=eq.alpaca&is_forecast=eq.false&select=ts" \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" | jq 'length'
