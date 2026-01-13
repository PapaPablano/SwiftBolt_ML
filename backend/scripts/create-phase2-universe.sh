#!/bin/bash
# Create Phase 2 Batch Jobs for Full Universe
# Uses all symbols from existing batch jobs

set -e

SUPABASE_URL="${SUPABASE_URL:-https://cygflaemtmwiwaviclks.supabase.co}"

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "❌ Error: SUPABASE_SERVICE_ROLE_KEY not set"
  exit 1
fi

echo "🚀 Creating Phase 2 Batch Jobs for Full Universe"
echo "================================================"
echo ""

# All 183 symbols from your existing batch jobs
SYMBOLS='["000660.KS","005930.KS","1120.SR","2222.SR","2330.TW","2473.HK","300001.SZ","300750.SZ","301510.SZ","301581.SZ","4569.TW","600519.SS","600941.SS","601225.SS","601328.SS","603160.SS","603444.SS","688390.SS","6981.T","7011.T","8058.T","8306.T","8942.TWO","A","A.BK","AA","AA.CN","AA.NE","AAPL","ABTC","ABXX.NE","ACN","AI","AI.BK","AI.MC","AI.NE","AI.PA","AI.TO","AI.VI","AIR.PA","AMAT","AMD","AMZ.BE","AMZ.DE","AMZ.DU","AMZ.F","AMZ.HA","AMZ.HM","AMZ.MU","AMZ.NE","AMZ.SG","AMZ.TG","AMZ.V","AMZN","APP","ASML.AS","AVGO","AXP","AZN.L","BBVA.MC","BHARTIARTL.NS","BHAT","BIT","BIT.AX","BITF.TO","BMNR","BRK.A","BTDR","CANF.TA","CO.PA","CRWD","DEXP3.SA","DIA","DIS","DKS","EAND.AD","EMAAR.DB","EMAARDEV.DB","ESLT.TA","EXX.JO","FICO","FRE.DE","GBTC","GDWN.L","GMG.AX","GMT.NZ","GOOG","GOOG.AS","GOOG.L","GOOG.MX","GOOG.NE","GOOG.TO","GOOGL","GOOS.TO","GSHD","GT","HABITAT.SN","HEN3.DE","HOOD","HSBA.L","IDXX","IHG.L","INGA.AS","INVE B.ST","ITX.MC","IWM","JNJ","JPM","KBC.BR","LIN","LLY","MA","META","MRK.DE","MSFT","MU","MU.MX","MU.NE","MU.VI","MUV2.DE","NDA.BE","NDA.DE","NDA.DU","NDA.F","NDA.HA","NDA.HM","NDA.MU","NDA.NE","NDA.SG","NDA.TG","NDA.V","NDA.VI","NFLX","NORBT.OL","NV.BK","NVDA","NXPI","ORCL","PL","PL.BK","PLTR","PRX.AS","QQQ","RACE.MI","RTX","SAAB B.ST","SHEL.L","SLB","SMPL","SPY","TAQA.AD","TJX","TMUS","TSLA","UMG.AS","UNH","V","VIX","VOXX","VZ","WMT","X.NE","X.PM","X.TO","XOM","XX.NE","XX.V","Z74.SI","ZBH","ZIM","ZIM.AX","ZIM.BE","ZIM.DU","ZIM.F","ZIM.HA","ZIM.HM","ZIM.MU","ZIM.SG","ZIM.TG"]'

SYMBOL_COUNT=$(echo "$SYMBOLS" | jq 'length')

echo "📊 Creating batch jobs for $SYMBOL_COUNT symbols"
echo "   Timeframes: m15, h1, h4, d1"
echo "   Batch size: 50 symbols per job"
echo "   Expected batches: $((SYMBOL_COUNT / 50 + 1)) per timeframe"
echo ""

# Create Phase 2 batch jobs
curl -X POST \
  "${SUPABASE_URL}/functions/v1/batch-backfill-orchestrator" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'Content-Type: application/json' \
  -d "{
    \"symbols\": ${SYMBOLS},
    \"timeframes\": [\"m15\", \"h1\", \"h4\", \"d1\"],
    \"sliceType\": \"historical\"
  }" | jq '.'

echo ""
echo "✅ Phase 2 batch jobs created!"
echo ""
echo "📈 Summary:"
echo "  - Total symbols: $SYMBOL_COUNT"
echo "  - Batches per timeframe: $((SYMBOL_COUNT / 50 + 1))"
echo "  - Total batch jobs: $((4 * (SYMBOL_COUNT / 50 + 1)))"
echo "  - API efficiency: ~50x improvement"
echo ""
echo "🔍 Next: Manually trigger orchestrator to start processing:"
echo "curl -X POST '${SUPABASE_URL}/functions/v1/orchestrator?action=tick' \\"
echo "  -H 'Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY'"
