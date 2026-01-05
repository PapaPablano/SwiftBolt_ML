# Data Integrity System: Historical + Intraday + Forecasts

## Problem Statement
Three independent data flows update the same chart without coordination:
- **Historical (Polygon)**: `adjusted=false`, sourced from API, 2-year lookback
- **Intraday (Tradier)**: Real-time quotes aggregated to daily bars, replaces historical for "today"
- **Forecasts (ML)**: Future predicted prices, completely separate from historical

Result: Massive swings on "problem days" because intraday overrides historical with different aggregation.

---

## Solution: Data Layering Architecture

Instead of mixing sources in one table, maintain **three separate logical layers**:

```
Historical Layer (Polygon, adjusted=false)
â”œâ”€ Immutable: dates before today
â”œâ”€ Provider: "polygon"
â”œâ”€ Fetch: Full 2-year backfill, daily aggregation
â””â”€ Update: Never updated once in DB

Intraday Layer (Tradier, real-time)
â”œâ”€ Today only
â”œâ”€ Provider: "tradier"
â”œâ”€ Fetch: 5-min bars during market hours
â”œâ”€ Aggregated to daily: only at close/EOD
â””â”€ Update: Every 15 minutes while market open

Forecast Layer (ML, unadjusted predictions)
â”œâ”€ Future only (t+1 to t+10 days)
â”œâ”€ Provider: "ml_forecast"
â”œâ”€ Fetch: Model output with confidence bands
â””â”€ Update: Once per day after market close
```

---

## Database Schema Changes

### New Table: `ohlc_bars_v2` (unified versioning)

```sql
CREATE TABLE ohlc_bars_v2 (
  id BIGINT PRIMARY KEY,
  symbol_id UUID NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  ts TIMESTAMP NOT NULL,
  
  -- OHLCV data
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  
  -- Data source tracking
  provider VARCHAR(20) NOT NULL,      -- "polygon", "tradier", "ml_forecast"
  is_intraday BOOLEAN DEFAULT false,  -- true if intraday aggregate
  is_forecast BOOLEAN DEFAULT false,  -- true if ML forecast
  data_status VARCHAR(20),            -- "verified", "live", "provisional"
  
  -- Freshness tracking
  fetched_at TIMESTAMP,               -- when this data was fetched
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  -- Confidence & metadata
  confidence_score DECIMAL(3, 2),     -- For forecasts: 0.0-1.0
  upper_band DECIMAL(10, 4),          -- For forecasts: upper CI
  lower_band DECIMAL(10, 4),          -- For forecasts: lower CI
  
  UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)
);

CREATE INDEX idx_chart_query ON ohlc_bars_v2(symbol_id, timeframe, ts DESC);
```

### Separation Rules (Hard Constraints)

```
Historical candles (ts < TODAY):
  âœ… Provider: "polygon"
  âœ… is_intraday: false
  âœ… is_forecast: false
  âœ… data_status: "verified"
  âŒ NEVER update once inserted

Intraday candles (ts = TODAY):
  âœ… Provider: "tradier"
  âœ… is_intraday: true during market hours
  âœ… is_forecast: false
  âœ… data_status: "live" (market open) â†’ "verified" (after close)
  âœ… Upsert: Every 15 min while market open
  âœ… Lock: 5 min after market close (prevent overwrites)

Forecast candles (ts > TODAY):
  âœ… Provider: "ml_forecast"
  âœ… is_intraday: false
  âœ… is_forecast: true
  âœ… data_status: "provisional" â†’ "verified" (if hit)
  âœ… Upsert: Once per day after market close
  âœ… Confidence band columns: populated from model output
```

---

## Chart Rendering Logic

### Query Pattern: Fetch All Three Layers

```sql
-- For a chart request covering last 60 days + 10 day forecast
SELECT * FROM ohlc_bars_v2
WHERE symbol_id = $1
  AND timeframe = $2
  AND (
    -- Historical: all completed days before today
    (ts < TODAY() AND is_forecast = false AND provider = 'polygon')
    OR
    -- Intraday: today's data from Tradier
    (ts = TODAY() AND is_intraday = true AND provider = 'tradier')
    OR
    -- Forecasts: t+1 to t+10
    (ts > TODAY() AND is_forecast = true AND provider = 'ml_forecast')
  )
ORDER BY ts ASC;
```

### Rendering Rules (Critical)

```javascript
// In chart rendering (Swift/JavaScript)

function renderChart(bars) {
  for (const bar of bars) {
    if (bar.is_forecast) {
      // Draw as dashed line + band shading
      drawForecast(bar);
    } else if (bar.is_intraday && bar.ts === TODAY) {
      // Draw with lighter color, mark as "live" if still trading
      drawIntradayCandle(bar, { opacity: 0.8, color: "blue" });
    } else {
      // Draw normal candlestick (historical)
      drawHistoricalCandle(bar);
    }
  }
}

// CRITICAL: Never mix layers
// âŒ DON'T do: blend intraday into historical average
// âœ… DO:       render as separate series
```

---

## Update Procedures

### Procedure 1: Historical Backfill (Polygon)

**When**: GitHub Action (weekly) or on-demand
**How**: UPSERT but **never update** rows with `ts < TODAY()`

```typescript
// backfill.ts
async function backfillHistorical(symbol: string) {
  const bars = await fetchPolygonBars(symbol, 730); // 2 years
  
  const rows = bars.map(bar => ({
    symbol_id: symbolId,
    timeframe: "d1",
    ts: bar.ts,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
    provider: "polygon",
    is_intraday: false,
    is_forecast: false,
    data_status: "verified",
    fetched_at: new Date(),
  }));
  
  // Insert only if row doesn't exist
  await supabase
    .from("ohlc_bars_v2")
    .insert(rows)
    .on("CONFLICT(symbol_id,timeframe,ts,provider,is_forecast)", "DO NOTHING");
}
```

### Procedure 2: Intraday Update (Tradier)

**When**: Every 15 min during market hours (9:30 AM â€“ 4:00 PM ET)
**How**: UPSERT only TODAY's data; lock after close

```typescript
// intraday-update.ts
async function updateIntraday(symbol: string) {
  const today = new Date().toISOString().split("T")[0];
  const market = await getMarketStatus();
  
  // 1. Fetch intraday bars
  const bars5min = await getTradierBars(symbol, "5min");
  const dailyAgg = aggregateToDaily(bars5min);
  
  // 2. Check if market is closed
  const isMarketClosed = market.state !== "open";
  
  const row = {
    symbol_id: symbolId,
    timeframe: "d1",
    ts: today,
    open: dailyAgg.open,
    high: dailyAgg.high,
    low: dailyAgg.low,
    close: dailyAgg.close,
    volume: dailyAgg.volume,
    provider: "tradier",
    is_intraday: true,
    is_forecast: false,
    data_status: isMarketClosed ? "verified" : "live",
    fetched_at: new Date(),
  };
  
  // 3. UPSERT today only (won't affect historical)
  await supabase
    .from("ohlc_bars_v2")
    .upsert([row], { 
      onConflict: "symbol_id,timeframe,ts,provider,is_forecast"
    });
}

// CRITICAL: After market close (4:15 PM ET), lock today's data
// â†’ Query should prioritize Tradier over Polygon for TODAY only
```

### Procedure 3: Forecast Update (ML)

**When**: Once per day after market close (5:00 PM ET)
**How**: UPSERT t+1 to t+10 days with confidence bands

```python
# ml_forecast_service.py
async def updateForecasts(symbol: str):
    """Generate and persist forecasts."""
    
    # 1. Get latest historical close (from Tradier if today, else Polygon)
    last_bar = await getLatestBar(symbol)
    
    # 2. Generate forecasts (t+1 to t+10)
    forecasts = await generateMLForecasts(
        symbol=symbol,
        basePrice=last_bar.close,
        horizonDays=10
    )
    
    # 3. Map to database rows
    rows = []
    for forecast in forecasts:
        rows.append({
            "symbol_id": symbol_id,
            "timeframe": "d1",
            "ts": forecast.targetDate,
            "open": None,  # Not applicable for forecasts
            "high": forecast.upper_band,  # Use band as proxy
            "low": forecast.lower_band,
            "close": forecast.midPrice,
            "volume": None,
            "provider": "ml_forecast",
            "is_intraday": False,
            "is_forecast": True,
            "data_status": "provisional",  # Will be "verified" if it hits
            "fetched_at": datetime.now(),
            "confidence_score": forecast.confidence,
            "upper_band": forecast.upper_band,
            "lower_band": forecast.lower_band,
        })
    
    # 4. Upsert (will overwrite previous forecast)
    supabase.table("ohlc_bars_v2").upsert(
        rows,
        on_conflict="symbol_id,timeframe,ts,provider,is_forecast"
    )
```

---

## Preventing Data Corruption: The Rules Engine

Create a **validation layer** before any write to `ohlc_bars_v2`:

```typescript
// data-validation.ts

interface WriteValidationRules {
  provider: string;
  ts: Date;
  isHistorical: boolean;
  
  validate(): { valid: boolean; reason?: string };
}

class PolygonHistoricalRule implements WriteValidationRules {
  provider = "polygon";
  
  validate(ts: Date): { valid: boolean; reason?: string } {
    const today = new Date().toISOString().split("T")[0];
    const barDate = ts.toISOString().split("T")[0];
    
    // Rule: Polygon writes only for dates BEFORE today
    if (barDate >= today) {
      return { 
        valid: false, 
        reason: "Polygon historical cannot write to today or future"
      };
    }
    
    return { valid: true };
  }
}

class TradierIntradayRule implements WriteValidationRules {
  provider = "tradier";
  
  validate(ts: Date): { valid: boolean; reason?: string } {
    const today = new Date().toISOString().split("T")[0];
    const barDate = ts.toISOString().split("T")[0];
    
    // Rule: Tradier writes only to TODAY
    if (barDate !== today) {
      return { 
        valid: false, 
        reason: "Tradier intraday must be for today only"
      };
    }
    
    // Rule: Lock writes 5 min after market close (4:05 PM ET)
    const now = new Date();
    const marketClose = new Date();
    marketClose.setHours(16, 0, 0, 0); // 4:00 PM ET
    const lockTime = new Date(marketClose.getTime() + 5 * 60 * 1000);
    
    if (now > lockTime) {
      return { 
        valid: false, 
        reason: "Today's data locked after 4:05 PM ET"
      };
    }
    
    return { valid: true };
  }
}

class MLForecastRule implements WriteValidationRules {
  provider = "ml_forecast";
  
  validate(ts: Date): { valid: boolean; reason?: string } {
    const today = new Date();
    
    // Rule: ML writes only for future dates
    if (ts <= today) {
      return { 
        valid: false, 
        reason: "ML forecasts must be for future dates only"
      };
    }
    
    // Rule: Maximum 10 days ahead
    const maxFuture = new Date(today.getTime() + 10 * 24 * 60 * 60 * 1000);
    if (ts > maxFuture) {
      return { 
        valid: false, 
        reason: "Forecasts cannot exceed 10 days ahead"
      };
    }
    
    return { valid: true };
  }
}

// Usage before any write
function validateWrite(provider: string, ts: Date): boolean {
  const rules = {
    polygon: new PolygonHistoricalRule(),
    tradier: new TradierIntradayRule(),
    ml_forecast: new MLForecastRule(),
  };
  
  const rule = rules[provider];
  if (!rule) return false;
  
  const result = rule.validate(ts);
  if (!result.valid) {
    logger.warn(`Blocked invalid write: ${result.reason}`);
  }
  return result.valid;
}
```

---

## Migration Plan (Zero Downtime)

### Phase 1: Create New Schema (1 hour)
- Create `ohlc_bars_v2` with new structure
- Run migration script to copy existing data, populating `provider` field

### Phase 2: Redirect Writes (parallel writes, 1 week)
- Update all Edge Functions to write to **both** tables
- Validate data matches between tables

### Phase 3: Redirect Reads (cutover, 1 hour)
- Update chart queries to read from `ohlc_bars_v2`
- Test thoroughly on staging

### Phase 4: Cleanup (optional)
- Archive old `ohlc_bars` table
- Delete when confident in new system

---

## Verification Checklist

- [ ] No historical data (ts < TODAY) is updated once inserted
- [ ] Intraday data (ts = TODAY, provider=tradier) locks after 4:05 PM ET
- [ ] Forecast data (ts > TODAY) has confidence bands populated
- [ ] Chart query uses correct layer priority: Today (Tradier) > Historical (Polygon) > Future (ML)
- [ ] Validation rules block bad writes with clear error messages
- [ ] Three layers render visually distinct (solid historical, lighter intraday, dashed forecasts)

---

## Expected Result

âœ… **Historical accuracy**: Polygon data never corrupted by intraday overrides
âœ… **Live precision**: Tradier updates only affect TODAY
âœ… **Forecast clarity**: ML bands separate from actual data
âœ… **No massive swings**: Each layer isolated and versioned
âœ… **Auditability**: `provider` + `fetched_at` tracks every row's origin
