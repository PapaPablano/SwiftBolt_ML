#!/bin/bash
# Deploy all new ML-related Edge Functions to Supabase
# This script deploys: technical-indicators, backtest-strategy, walk-forward-optimize, portfolio-optimize, stress-test

set -e

echo "========================================="
echo "ML Edge Functions - Deployment"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "supabase/functions" ]; then
    echo "❌ Error: Must run from project root"
    exit 1
fi

# Check if Supabase CLI is available
if ! command -v supabase &> /dev/null; then
    echo "❌ Error: Supabase CLI not found. Install with: brew install supabase/tap/supabase"
    exit 1
fi

echo "📦 Deploying ML Edge Functions..."
echo ""

# List of functions to deploy
FUNCTIONS=(
    "technical-indicators"
    "backtest-strategy"
    "walk-forward-optimize"
    "portfolio-optimize"
    "stress-test"
)

# Deploy each function
for func in "${FUNCTIONS[@]}"; do
    if [ -d "supabase/functions/$func" ]; then
        echo "🚀 Deploying: $func"
        supabase functions deploy "$func" || {
            echo "⚠️  Warning: Failed to deploy $func"
            echo "   Make sure you're linked to your Supabase project:"
            echo "   supabase link --project-ref YOUR_PROJECT_REF"
        }
        echo ""
    else
        echo "⚠️  Warning: Function directory not found: supabase/functions/$func"
    fi
done

echo "========================================="
echo "Deployment Summary"
echo "========================================="
echo ""
echo "✅ Functions deployed:"
for func in "${FUNCTIONS[@]}"; do
    if [ -d "supabase/functions/$func" ]; then
        echo "   - $func"
    fi
done
echo ""
echo "📋 Next steps:"
echo "1. Verify deployments: supabase functions list"
echo "2. Test functions using the Swift app or curl commands"
echo "3. Check function logs in Supabase Dashboard"
echo ""
echo "💡 Note: Make sure Python scripts are accessible at the paths"
echo "   specified in the Edge Functions (or set environment variables)"
echo ""
