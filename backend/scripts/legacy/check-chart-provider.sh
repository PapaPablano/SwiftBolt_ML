#!/bin/bash
set -e

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "Fetching AAPL h1 chart data (60 days)..."
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "apikey: $ANON_KEY" \
  -d '{"symbol":"AAPL","timeframe":"h1","days":60}' \
  "$SUPABASE_URL/functions/v1/chart-data-v2")

echo "Metadata and provider info:"
echo "$RESPONSE" | jq '{
  total_bars: .metadata.total_bars,
  historical: {
    count: .layers.historical.count,
    provider: .layers.historical.provider
  },
  intraday: {
    count: .layers.intraday.count,
    provider: .layers.intraday.provider
  }
}'

echo ""
echo "Sample of historical bars (first 3):"
echo "$RESPONSE" | jq '.layers.historical.data[:3] | .[] | {ts, provider}'

echo ""
echo "Sample of intraday bars (first 3):"
echo "$RESPONSE" | jq '.layers.intraday.data[:3] | .[] | {ts, provider}'
