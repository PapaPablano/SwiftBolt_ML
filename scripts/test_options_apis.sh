#!/usr/bin/env bash
# Test all Options Ranker APIs to diagnose $0.00 quote issues
# Usage: ./scripts/test_options_apis.sh [CONTRACT_SYMBOL]
# Example: ./scripts/test_options_apis.sh AAPL280316C00310000

set -e
SYMBOL="${1:-AAPL}"
CONTRACT="${2:-AAPL280316C00310000}"  # AAPL $310 CALL March 16 2028

# Load env if available
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

SUPABASE_URL="${SUPABASE_URL:-https://cygflaemtmwiwaviclks.supabase.co}"
ANON_KEY="${SUPABASE_ANON_KEY:-}"
FASTAPI_URL="${FASTAPI_URL:-http://localhost:8000}"

if [ -z "$ANON_KEY" ]; then
  echo "⚠️  SUPABASE_ANON_KEY not set. Set it in .env or export it."
  echo "   Some tests may fail without auth."
fi

CURL_AUTH=()
[ -n "$ANON_KEY" ] && CURL_AUTH=(-H "Authorization: Bearer $ANON_KEY" -H "apikey: $ANON_KEY")

echo "=========================================="
echo "Options API Test - $SYMBOL / $CONTRACT"
echo "=========================================="
echo ""

# 1. Options rankings (from options_ranks / Supabase)
echo "1️⃣  OPTIONS-RANKINGS (ranks from DB)"
echo "   GET .../options-rankings?symbol=$SYMBOL&limit=5"
echo "---"
curl -s -w "\n   HTTP %{http_code}" \
  "${CURL_AUTH[@]}" \
  "${SUPABASE_URL}/functions/v1/options-rankings?symbol=${SYMBOL}&limit=5&mode=monitor" \
  | head -c 800
echo ""
echo ""

# 2. Options chain (full chain - FastAPI then Edge)
echo "2️⃣  OPTIONS-CHAIN (full chain)"
echo "   GET .../options-chain?underlying=$SYMBOL"
echo "---"
# Try FastAPI first
R=$(curl -s -w "\n%{http_code}" -m 5 "${FASTAPI_URL}/api/v1/options-chain?underlying=${SYMBOL}" 2>/dev/null || echo "000")
CODE=$(echo "$R" | tail -1)
BODY=$(echo "$R" | sed '$d')
if [ "$CODE" = "200" ]; then
  echo "   [FastAPI] HTTP $CODE"
  echo "$BODY" | head -c 600
else
  echo "   [FastAPI] HTTP $CODE (or timeout) - trying Edge..."
  curl -s -w "\n   HTTP %{http_code}" "${CURL_AUTH[@]}" \
    "${SUPABASE_URL}/functions/v1/options-chain?underlying=${SYMBOL}" \
    | head -c 600
fi
echo ""
echo ""

# 3. Options quotes (bid/ask/mark for specific contracts)
echo "3️⃣  OPTIONS-QUOTES (bid/ask/mark for $CONTRACT)"
echo "   POST .../options-quotes  body: {\"symbol\":\"$SYMBOL\",\"contracts\":[\"$CONTRACT\"]}"
echo "---"
# Try FastAPI first
R=$(curl -s -w "\n%{http_code}" -m 10 -X POST "${FASTAPI_URL}/api/v1/options-quotes" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$SYMBOL\",\"contracts\":[\"$CONTRACT\"]}" 2>/dev/null || echo "000")
CODE=$(echo "$R" | tail -1)
BODY=$(echo "$R" | sed '$d')
if [ "$CODE" = "200" ]; then
  echo "   [FastAPI] HTTP $CODE"
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
  echo "   [FastAPI] HTTP $CODE (or timeout) - trying Edge..."
  curl -s -X POST "${SUPABASE_URL}/functions/v1/options-quotes" \
    "${CURL_AUTH[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\":\"$SYMBOL\",\"contracts\":[\"$CONTRACT\"]}" \
    | python3 -m json.tool 2>/dev/null || cat
fi
echo ""
echo ""

# 4. Check if contract exists in chain (find a near-term contract with data)
echo "4️⃣  SPOT-CHECK: AAPL near-term call (next 30 days)"
# Use a common near-term format - e.g. AAPL260206C00280000 (Feb 6 2026, $280 call)
NEAR_CONTRACT="AAPL260206C00280000"
echo "   POST .../options-quotes  contracts: [$NEAR_CONTRACT]"
echo "---"
curl -s -X POST "${SUPABASE_URL}/functions/v1/options-quotes" \
  "${CURL_AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"AAPL\",\"contracts\":[\"$NEAR_CONTRACT\"]}" \
  | python3 -m json.tool 2>/dev/null || cat
echo ""
echo ""

echo "=========================================="
echo "Summary: $0.00 usually means (1) provider has no quote for that contract,"
echo "(2) contract symbol format wrong, or (3) options-quotes returned empty."
echo "Deep OTM / long-dated options often have no bid/ask from some providers."
echo "=========================================="
