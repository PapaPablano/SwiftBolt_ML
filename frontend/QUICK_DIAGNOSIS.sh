#!/bin/bash
# Quick diagnosis for Polynomial S&R wiring issue

echo "🔍 POLYNOMIAL S&R WIRING DIAGNOSIS"
echo "=================================="
echo ""

echo "1️⃣ Checking if backend API is responding..."
RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Backend API responding (200 OK)"
    if echo "$BODY" | grep -q "polynomial_support"; then
        echo "✅ API returns polynomial_support data"
        SUPPORT=$(echo "$BODY" | grep -o '"level":[0-9.]*' | head -1)
        echo "   Support data: $SUPPORT"
    else
        echo "❌ API response missing polynomial_support"
        echo "   Response: ${BODY:0:200}..."
    fi
elif [ "$HTTP_CODE" = "404" ]; then
    echo "❌ Backend endpoint not found (404)"
    echo "   Check: is backend running on localhost:8000?"
    echo "   Run: cd /Users/ericpeterson/SwiftBolt_ML/ml && python -m uvicorn main:app --reload"
else
    echo "❌ Backend error (HTTP $HTTP_CODE)"
    echo "   Response: ${BODY:0:200}..."
fi

echo ""
echo "2️⃣ Checking frontend files..."
for file in "src/hooks/useIndicators.ts" "src/components/IndicatorPanel.tsx" "src/components/ChartWithIndicators.tsx"; do
    if [ -f "frontend/$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file MISSING"
    fi
done

echo ""
echo "3️⃣ Checking imports..."
if grep -q "ChartWithIndicators" frontend/src/App.tsx 2>/dev/null; then
    echo "✅ App.tsx imports ChartWithIndicators"
else
    echo "❌ App.tsx doesn't import ChartWithIndicators"
fi

if grep -q "srData" frontend/src/components/TradingViewChart.tsx 2>/dev/null; then
    echo "✅ TradingViewChart.tsx has srData prop"
else
    echo "❌ TradingViewChart.tsx missing srData prop"
fi

if grep -q "useIndicators" frontend/src/components/ChartWithIndicators.tsx 2>/dev/null; then
    echo "✅ ChartWithIndicators uses useIndicators hook"
else
    echo "❌ ChartWithIndicators missing useIndicators hook"
fi

echo ""
echo "🔧 NEXT STEPS:"
echo "============="
echo "1. Open browser DevTools (F12)"
echo "2. Go to Console tab and look for logs:"
echo "   - Should see: '[Chart] Updated S/R: Support ...'"
echo "   - Should see: API calls every 30 seconds"
echo ""
echo "3. Go to Network tab"
echo "4. Switch symbol or reload"
echo "5. Look for: GET /api/support-resistance"
echo "   - Status should be 200"
echo "   - Response should have 'polynomial_support' and 'polynomial_resistance'"
echo ""
echo "6. If API returns data but chart shows nothing:"
echo "   - The wiring between useIndicators → TradingViewChart is broken"
echo "   - Check srData prop is passed to TradingViewChart"
echo ""
echo "For detailed debugging, see: frontend/DEBUG_POLYNOMIAL_SR.md"
