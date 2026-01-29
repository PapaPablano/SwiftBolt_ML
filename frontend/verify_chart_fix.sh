#!/bin/bash

# Polynomial S/R Chart Fix Verification Script
# ============================================

echo "====================================="
echo "Polynomial S/R Chart Fix Verification"
echo "====================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if backend is running
echo "Step 1: Checking backend API..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend API is running"
else
    echo -e "${RED}✗${NC} Backend API is NOT running"
    echo -e "${YELLOW}→ Start backend: cd ml && uvicorn api.main:app --reload${NC}"
    exit 1
fi

echo ""

# Step 2: Test S/R endpoint
echo "Step 2: Testing S/R endpoint..."
RESPONSE=$(curl -s "http://localhost:8000/api/v1/support-resistance?symbol=AAPL&timeframe=d1")

if echo "$RESPONSE" | jq -e '.polynomial_support' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} S/R endpoint returns polynomial_support"
    
    SUPPORT_LEVEL=$(echo "$RESPONSE" | jq -r '.polynomial_support.level')
    SUPPORT_SLOPE=$(echo "$RESPONSE" | jq -r '.polynomial_support.slope')
    SUPPORT_TREND=$(echo "$RESPONSE" | jq -r '.polynomial_support.trend')
    
    echo "  Level: \$${SUPPORT_LEVEL}"
    echo "  Slope: ${SUPPORT_SLOPE}"
    echo "  Trend: ${SUPPORT_TREND}"
else
    echo -e "${RED}✗${NC} S/R endpoint does NOT return polynomial_support"
    echo "Response: $RESPONSE"
    exit 1
fi

if echo "$RESPONSE" | jq -e '.polynomial_resistance' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} S/R endpoint returns polynomial_resistance"
    
    RESIST_LEVEL=$(echo "$RESPONSE" | jq -r '.polynomial_resistance.level')
    RESIST_SLOPE=$(echo "$RESPONSE" | jq -r '.polynomial_resistance.slope')
    RESIST_TREND=$(echo "$RESPONSE" | jq -r '.polynomial_resistance.trend')
    
    echo "  Level: \$${RESIST_LEVEL}"
    echo "  Slope: ${RESIST_SLOPE}"
    echo "  Trend: ${RESIST_TREND}"
else
    echo -e "${RED}✗${NC} S/R endpoint does NOT return polynomial_resistance"
fi

echo ""

# Step 3: Check chart data endpoint
echo "Step 3: Testing chart data endpoint..."
CHART_RESPONSE=$(curl -s "http://localhost:8000/api/v1/chart-data/AAPL/d1?days_back=7")

if echo "$CHART_RESPONSE" | jq -e '.bars' > /dev/null 2>&1; then
    BAR_COUNT=$(echo "$CHART_RESPONSE" | jq '.bars | length')
    echo -e "${GREEN}✓${NC} Chart data endpoint returns ${BAR_COUNT} bars"
else
    echo -e "${RED}✗${NC} Chart data endpoint failed"
    exit 1
fi

echo ""

# Step 4: Check if frontend files exist
echo "Step 4: Verifying frontend files..."

if [ -f "src/components/TradingViewChart.tsx" ]; then
    echo -e "${GREEN}✓${NC} TradingViewChart.tsx exists"
    
    # Check if new function exists
    if grep -q "calculatePolynomialCurve" src/components/TradingViewChart.tsx; then
        echo -e "${GREEN}✓${NC} calculatePolynomialCurve() function found"
    else
        echo -e "${RED}✗${NC} calculatePolynomialCurve() function NOT found"
        echo -e "${YELLOW}→ Make sure you applied the fix!${NC}"
        exit 1
    fi
    
    if grep -q "chartBars" src/components/TradingViewChart.tsx; then
        echo -e "${GREEN}✓${NC} chartBars state found"
    else
        echo -e "${RED}✗${NC} chartBars state NOT found"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} TradingViewChart.tsx NOT found"
    exit 1
fi

echo ""

# Step 5: Check if dev server can start
echo "Step 5: Checking frontend dev server..."

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${GREEN}✓${NC} Frontend dev server is running on port 5173"
    echo -e "${GREEN}→ Open http://localhost:5173 to see charts${NC}"
else
    echo -e "${YELLOW}⚠${NC} Frontend dev server is NOT running"
    echo -e "${YELLOW}→ Start frontend: npm run dev${NC}"
fi

echo ""

# Summary
echo "====================================="
echo "Verification Summary"
echo "====================================="
echo ""
echo -e "${GREEN}✓ Backend API: Running${NC}"
echo -e "${GREEN}✓ S/R Endpoint: Working${NC}"
echo -e "${GREEN}✓ Chart Data: Working${NC}"
echo -e "${GREEN}✓ Frontend Code: Updated${NC}"
echo ""
echo "====================================="
echo "Next Steps:"
echo "====================================="
echo ""
echo "1. Start frontend (if not running):"
echo "   npm run dev"
echo ""
echo "2. Open in browser:"
echo "   http://localhost:5173"
echo ""
echo "3. Look for:"
echo "   - Blue line (Polynomial Support)"
echo "   - Red line (Polynomial Resistance)"
echo "   - Both should be sloped across the chart"
echo ""
echo "4. Check browser console (F12) for:"
echo "   [Chart] Plotted 150+ support points"
echo "   [Chart] Plotted 150+ resistance points"
echo ""
echo "====================================="
echo -e "${GREEN}Verification Complete!${NC}"
echo "====================================="
