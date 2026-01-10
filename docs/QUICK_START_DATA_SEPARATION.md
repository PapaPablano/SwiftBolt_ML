# Quick Start: Data Layer Separation Deployment

## Prerequisites
- Access to Supabase Dashboard (SQL Editor)
- GitHub repository access for workflows
- Environment variables configured

## Step 1: Deploy Migrations (5 minutes)

### Go to Supabase Dashboard → SQL Editor

Execute these two migrations in order:

### Migration 1: Create ohlc_bars_v2 Table

```sql
-- Copy the entire contents of:
-- backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql
```

**Or execute this directly:**

<details>
<summary>Click to expand SQL</summary>

```sql
-- Create the new versioned OHLC table
CREATE TABLE IF NOT EXISTS ohlc_bars_v2 (
  id BIGSERIAL PRIMARY KEY,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  timeframe VARCHAR(10) NOT NULL,
  ts TIMESTAMP NOT NULL,
  
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  
  provider VARCHAR(20) NOT NULL CHECK (provider IN ('polygon', 'tradier', 'ml_forecast')),
  is_intraday BOOLEAN DEFAULT false,
  is_forecast BOOLEAN DEFAULT false,
  data_status VARCHAR(20) CHECK (data_status IN ('verified', 'live', 'provisional')),
  
  fetched_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  confidence_score DECIMAL(3, 2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
  upper_band DECIMAL(10, 4),
  lower_band DECIMAL(10, 4),
  
  UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)
);

CREATE INDEX idx_ohlc_v2_chart_query ON ohlc_bars_v2(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_ohlc_v2_provider ON ohlc_bars_v2(provider, ts DESC);
CREATE INDEX idx_ohlc_v2_forecast ON ohlc_bars_v2(is_forecast, ts) WHERE is_forecast = true;
CREATE INDEX idx_ohlc_v2_intraday ON ohlc_bars_v2(is_intraday, ts) WHERE is_intraday = true;

-- Validation triggers (see full migration file for complete implementation)
```

</details>

### Migration 2: Migrate Existing Data

```sql
-- Copy the entire contents of:
-- backend/supabase/migrations/20260105000001_migrate_to_v2.sql
```

**Or execute this directly:**

<details>
<summary>Click to expand SQL</summary>

```sql
INSERT INTO ohlc_bars_v2 (
  symbol_id, timeframe, ts, open, high, low, close, volume,
  provider, is_intraday, is_forecast, data_status, fetched_at, created_at
)
SELECT 
  symbol_id, timeframe, ts, open, high, low, close, volume,
  CASE WHEN provider IN ('massive', 'polygon') THEN 'polygon' ELSE 'polygon' END as provider,
  false as is_intraday,
  false as is_forecast,
  'verified' as data_status,
  COALESCE(fetched_at, created_at, now()) as fetched_at,
  created_at
FROM ohlc_bars
WHERE DATE(ts) < CURRENT_DATE
ON CONFLICT (symbol_id, timeframe, ts, provider, is_forecast) DO NOTHING;
```

</details>

### Verify Migration Success

```sql
-- Check table exists and has data
SELECT 
  COUNT(*) as total_bars,
  provider,
  is_intraday,
  is_forecast,
  data_status
FROM ohlc_bars_v2
GROUP BY provider, is_intraday, is_forecast, data_status;

-- Expected result: rows with provider='polygon', is_intraday=false, is_forecast=false
```

## Step 2: Test Historical Backfill (2 minutes)

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Test with AAPL
python ml/src/scripts/deep_backfill_ohlc_v2.py --symbol AAPL

# Expected output:
# ✅ Fetched 499 historical bars for AAPL d1
# ✅ Persisted 499 historical bars for AAPL d1
```

**Verify in Supabase:**
```sql
SELECT COUNT(*) as bar_count,
       MIN(ts) as earliest,
       MAX(ts) as latest
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND provider = 'polygon'
  AND is_forecast = false;
```

## Step 3: Test ML Forecasts (1 minute)

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Generate forecasts for AAPL
python -m ml.src.services.forecast_service_v2 --symbol AAPL --horizon 10

# Expected output:
# ✅ Persisted 10 forecasts for AAPL
```

**Verify in Supabase:**
```sql
SELECT ts, close, upper_band, lower_band, confidence_score
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND provider = 'ml_forecast'
  AND is_forecast = true
ORDER BY ts ASC
LIMIT 10;
```

## Step 4: Deploy Edge Function (Optional)

```bash
cd backend/supabase

# Deploy chart-data-v2 function
supabase functions deploy chart-data-v2
```

**Test the endpoint:**
```bash
curl -X POST \
  "https://your-project.supabase.co/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "days": 60,
    "includeForecast": true,
    "forecastDays": 10
  }'
```

## Step 5: Update Client Code

### Swift (macOS Client)

```swift
// Update chart data fetching
struct ChartDataV2Response: Codable {
    let symbol: String
    let timeframe: String
    let layers: ChartLayers
    let metadata: ChartMetadata
}

struct ChartLayers: Codable {
    let historical: LayerData
    let intraday: LayerData
    let forecast: LayerData
}

struct LayerData: Codable {
    let count: Int
    let provider: String
    let data: [OHLCBar]
}

// Fetch chart data
func fetchChartData(symbol: String) async throws -> ChartDataV2Response {
    let url = URL(string: "\(supabaseURL)/functions/v1/chart-data-v2")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("Bearer \(supabaseKey)", forHTTPHeaderField: "Authorization")
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let body = [
        "symbol": symbol,
        "days": 60,
        "includeForecast": true,
        "forecastDays": 10
    ]
    request.httpBody = try JSONEncoder().encode(body)
    
    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode(ChartDataV2Response.self, from: data)
}

// Render with layer separation
func renderChart(data: ChartDataV2Response) {
    // Historical bars (solid)
    for bar in data.layers.historical.data {
        drawCandlestick(bar, style: .solid, color: .primary)
    }
    
    // Intraday bar (highlighted)
    for bar in data.layers.intraday.data {
        drawCandlestick(bar, style: .solid, color: .blue, opacity: 0.8)
    }
    
    // Forecast bars (dashed with confidence bands)
    for bar in data.layers.forecast.data {
        drawForecast(bar, style: .dashed, showBands: true)
    }
}
```

### TypeScript/JavaScript

```typescript
interface ChartDataV2Response {
  symbol: string;
  timeframe: string;
  layers: {
    historical: { count: number; provider: string; data: OHLCBar[] };
    intraday: { count: number; provider: string; data: OHLCBar[] };
    forecast: { count: number; provider: string; data: OHLCBar[] };
  };
  metadata: {
    total_bars: number;
    start_date: string;
    end_date: string;
  };
}

async function fetchChartData(symbol: string): Promise<ChartDataV2Response> {
  const response = await fetch(`${SUPABASE_URL}/functions/v1/chart-data-v2`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      symbol,
      days: 60,
      includeForecast: true,
      forecastDays: 10,
    }),
  });
  
  return response.json();
}

// Render with TradingView or Chart.js
function renderChart(data: ChartDataV2Response) {
  const chart = createChart(container);
  
  // Historical series (candlestick)
  const historicalSeries = chart.addCandlestickSeries({
    upColor: '#26a69a',
    downColor: '#ef5350',
  });
  historicalSeries.setData(data.layers.historical.data);
  
  // Intraday overlay (different color)
  const intradaySeries = chart.addCandlestickSeries({
    upColor: '#4a90e2',
    downColor: '#e24a4a',
    opacity: 0.8,
  });
  intradaySeries.setData(data.layers.intraday.data);
  
  // Forecast series (line with bands)
  const forecastSeries = chart.addLineSeries({
    color: '#9c27b0',
    lineStyle: 2, // dashed
  });
  forecastSeries.setData(
    data.layers.forecast.data.map(bar => ({
      time: bar.ts,
      value: bar.close,
    }))
  );
  
  // Add confidence bands
  const bandSeries = chart.addAreaSeries({
    topColor: 'rgba(156, 39, 176, 0.2)',
    bottomColor: 'rgba(156, 39, 176, 0.05)',
  });
  bandSeries.setData(
    data.layers.forecast.data.map(bar => ({
      time: bar.ts,
      value: bar.upper_band,
    }))
  );
}
```

## Step 6: Enable GitHub Actions

### Verify Secrets

Go to GitHub → Settings → Secrets and variables → Actions

Ensure these secrets exist:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `TRADIER_TOKEN`
- `MASSIVE_API_KEY`

### Enable Workflow

The workflow `.github/workflows/intraday-update-v2.yml` will automatically:
- Run every 15 minutes during market hours (9:30 AM - 4:15 PM ET)
- Update intraday data for all watchlist symbols
- Lock writes at 4:05 PM ET

**Manual test:**
1. Go to GitHub Actions
2. Select "Intraday Update V2 (Tradier)"
3. Click "Run workflow"
4. Enter test symbols: `AAPL,NVDA`
5. Check logs for success

## Verification Checklist

Run these queries to verify everything is working:

```sql
-- 1. Check data layer distribution
SELECT 
  provider,
  is_intraday,
  is_forecast,
  COUNT(*) as bar_count,
  MIN(DATE(ts)) as earliest_date,
  MAX(DATE(ts)) as latest_date
FROM ohlc_bars_v2
GROUP BY provider, is_intraday, is_forecast
ORDER BY provider, is_intraday, is_forecast;

-- Expected:
-- polygon  | false | false | ~500+ | 2024-01-xx | 2026-01-04
-- tradier  | true  | false | 0-1   | 2026-01-05 | 2026-01-05 (if market open)
-- ml_forecast | false | true | 10+ | 2026-01-06 | 2026-01-15

-- 2. Verify no data corruption (historical data unchanged)
SELECT COUNT(*) as historical_bars_today
FROM ohlc_bars_v2
WHERE DATE(ts) = CURRENT_DATE
  AND provider = 'polygon';
-- Expected: 0 (polygon should never write to today)

-- 3. Check validation rules are active
SELECT COUNT(*) FROM pg_trigger 
WHERE tgname = 'ohlc_v2_validation_trigger';
-- Expected: 1

-- 4. Test chart query function
SELECT * FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'd1',
  NOW() - INTERVAL '60 days',
  NOW() + INTERVAL '10 days'
) LIMIT 5;
```

## Success Criteria

✅ **ohlc_bars_v2 table created** with proper schema  
✅ **Historical data migrated** from ohlc_bars  
✅ **AAPL backfill successful** (~500 bars)  
✅ **AAPL forecasts generated** (10 bars)  
✅ **Chart API returns three layers** correctly  
✅ **Client renders layers distinctly**  
✅ **GitHub Action runs successfully**  
✅ **No data corruption** (historical unchanged)  

## Troubleshooting

### Issue: Table not found
**Solution:** Run migrations in Supabase SQL Editor

### Issue: Validation errors
**Solution:** Check that provider, is_intraday, is_forecast match the rules

### Issue: No intraday data
**Solution:** Market must be open, or within 5 min of close

### Issue: Forecasts fail
**Solution:** Ensure historical data exists first (base price needed)

## Next Steps

1. ✅ Deploy migrations
2. ✅ Test backfill
3. ✅ Test forecasts
4. ✅ Update client apps
5. ✅ Enable workflows
6. Monitor for 1 week
7. Archive old `ohlc_bars` table

## Support

For issues, check:
- `DATA_LAYER_SEPARATION_IMPLEMENTATION.md` - Full implementation details
- `DEPLOYMENT_INSTRUCTIONS.md` - Detailed deployment guide
- `dataintegrity.md` - Original problem analysis
