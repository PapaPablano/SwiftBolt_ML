#!/bin/bash
# Deploy internal Supabase Edge Functions with JWT verification disabled
# These functions are called server-to-server or by GitHub Actions with service keys

set -e

echo "========================================="
echo "Deploy Internal Edge Functions (No JWT)"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "backend/supabase/functions" ]; then
    echo "Error: Must run from project root"
    exit 1
fi

cd backend/supabase

# List of internal functions that should NOT verify JWT
# These are called by:
# - GitHub Actions with service role keys
# - Other edge functions (server-to-server)
# - pg_cron jobs

INTERNAL_FUNCTIONS=(
    "symbol-init"
    "reload-watchlist-data"
    "chart-data-v2"
    "chart"
    "fetch-bars"
    "orchestrator"
    "intraday-update"
    "options-scrape"
    "refresh-data"
    "enhanced-prediction"
    "symbols-search"
    "news"
)

echo "Deploying ${#INTERNAL_FUNCTIONS[@]} internal functions..."
echo ""

deployed=0
failed=0

for func in "${INTERNAL_FUNCTIONS[@]}"; do
    if [ -d "functions/$func" ]; then
        echo "Deploying $func (--no-verify-jwt)..."
        if supabase functions deploy "$func" --no-verify-jwt 2>&1; then
            echo "  ✅ $func deployed"
            ((deployed++))
        else
            echo "  ❌ $func FAILED"
            ((failed++))
        fi
    else
        echo "  ⚠️  $func not found (skipping)"
    fi
done

echo ""
echo "========================================="
echo "Deployment Summary"
echo "========================================="
echo "Deployed: $deployed"
echo "Failed:   $failed"
echo ""

if [ $failed -gt 0 ]; then
    echo "⚠️  Some deployments failed. Check errors above."
    exit 1
else
    echo "✅ All internal functions deployed successfully!"
fi

echo ""
echo "Next steps:"
echo "1. Verify functions work by calling reload-watchlist-data:"
echo "   curl -X POST \\"
echo "     \$SUPABASE_URL/functions/v1/reload-watchlist-data \\"
echo "     -H \"Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"symbols\": [\"AAPL\"], \"forceRefresh\": true}'"
echo ""
echo "2. Run GitHub Action 'Alpaca Intraday Update' manually to test"
echo ""
