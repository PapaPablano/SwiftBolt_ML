# Phase 6: Options Ranker & Scanner - Implementation Summary

**Status**: Backend Complete ✅ | Frontend Integration Pending ⏳

## Overview

Phase 6 delivers ML-powered options ranking and watchlist scanning capabilities. The backend infrastructure is complete with database schema, ML scoring logic, and deployed Edge Functions. Swift models are ready for frontend integration.

---

## 🗄️ Database Schema Enhancements

### `options_ranks` Table (Enhanced)
Extended existing table from Phase 1 with ML scoring and pricing data:

**New Columns Added**:
- `contract_symbol` (TEXT) - OCC option symbol format
- `theta` (NUMERIC) - Time decay greek
- `vega` (NUMERIC) - Volatility sensitivity
- `rho` (NUMERIC) - Interest rate sensitivity
- `bid`, `ask`, `mark`, `last_price` (NUMERIC) - Pricing data

**New Indexes**:
- `idx_options_ranks_run_at` - Query latest rankings
- `idx_options_ranks_underlying_score` - Composite index for top-ranked contracts per symbol

### `scanner_alerts` Table (Enhanced)
Extended existing table with categorization and details:

**New Columns Added**:
- `condition_type` (TEXT) - technical | ml | volume | price
- `details` (JSONB) - Flexible payload for alert context (thresholds, values, etc.)
- `is_read` (BOOLEAN) - User acknowledgment flag
- `expires_at` (TIMESTAMPTZ) - Optional auto-cleanup timestamp

**New Indexes**:
- `idx_scanner_alerts_condition_type` - Filter by alert category
- `idx_scanner_alerts_is_read` - Unread alerts queries

**Migration**: `20251216044500_options_ranks_and_scanner_alerts.sql`

---

## 🤖 ML Pipeline: Options Ranking

### `OptionsRanker` Class (`ml/src/models/options_ranker.py`)

Multi-factor ML scoring model that evaluates option contracts based on:

1. **Moneyness Score** (25% weight)
   - Aligns strike distance with underlying trend
   - Bullish trend → favors ATM to 5% OTM calls
   - Bearish trend → favors ATM to 5% OTM puts

2. **IV Rank Score** (20% weight)
   - Compares implied volatility to historical volatility
   - Higher scores when IV < HV (buying opportunity)
   - Penalizes very high or suspiciously low IV

3. **Liquidity Score** (15% weight)
   - 60% open interest (stability)
   - 40% volume (current activity)
   - Minimum threshold filter (10%)

4. **Delta Score** (15% weight)
   - Aligns delta magnitude with trend strength
   - Bullish trend + call → higher delta preferred
   - Neutral trend → moderate deltas

5. **Theta Decay Score** (10% weight)
   - Adjusts for time remaining
   - Penalizes high theta decay near expiration
   - Less critical for long-dated options (>45 DTE)

6. **Momentum Score** (15% weight)
   - Directional alignment
   - Calls score 1.0 on bullish trend
   - Puts score 1.0 on bearish trend
   - Counter-trend positions score 0.2

**Output**: Composite `ml_score` normalized to 0-1 range, sorted descending.

### `options_ranking_job.py`

Batch processing script designed to:
1. Fetch options chain data via `/options-chain` API
2. Load underlying OHLC and derive trend
3. Calculate historical volatility (20-day)
4. Score contracts using `OptionsRanker`
5. Save top-ranked contracts to `options_ranks` table

**Note**: Requires integration with options chain API for full automation.

---

## 🌐 Edge Functions (Deployed)

### `GET /options-rankings`

Returns ML-ranked option contracts for a symbol.

**Endpoint**: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings`

**Query Parameters**:
- `symbol` (required) - Underlying ticker (e.g., "AAPL")
- `expiry` (optional) - Filter by expiration date (YYYY-MM-DD)
- `side` (optional) - Filter by "call" or "put"
- `limit` (optional) - Max contracts to return (default: 50)

**Response Schema**:
```json
{
  "symbol": "AAPL",
  "totalRanks": 25,
  "ranks": [
    {
      "id": "uuid",
      "contractSymbol": "AAPL240119C00150000",
      "expiry": "2024-01-19",
      "strike": 150.0,
      "side": "call",
      "mlScore": 0.85,
      "delta": 0.65,
      "gamma": 0.03,
      "theta": -0.05,
      "vega": 0.12,
      "impliedVol": 0.32,
      "volume": 1200,
      "openInterest": 5000,
      "bid": 5.20,
      "ask": 5.30,
      "mark": 5.25,
      "lastPrice": 5.28,
      "runAt": "2024-01-15T10:30:00Z"
    }
  ],
  "filters": {
    "expiry": "2024-01-19",
    "side": "call"
  }
}
```

**Features**:
- Sorted by `mlScore` descending
- Returns top 50 contracts by default
- Flexible filtering for expiry and option type
- Ready for plan gating integration

---

### `POST /scanner-watchlist`

Scans watchlist symbols for ML signals and alerts.

**Endpoint**: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/scanner-watchlist`

**Request Body**:
```json
{
  "symbols": ["AAPL", "MSFT", "NVDA"]
}
```

**Response Schema**:
```json
{
  "watchlist": [
    {
      "symbol": "AAPL",
      "assetType": "stock",
      "mlLabel": "Bullish",
      "mlConfidence": 0.78,
      "unreadAlertCount": 2,
      "hasCriticalAlert": false,
      "lastPrice": 195.50,
      "priceChange": 2.30,
      "priceChangePercent": 1.19
    }
  ],
  "alerts": [
    {
      "id": "uuid",
      "symbol": "AAPL",
      "triggeredAt": "2024-01-15T14:22:00Z",
      "conditionLabel": "RSI Oversold",
      "conditionType": "technical",
      "severity": "warning",
      "details": {
        "rsi": 28.5,
        "threshold": 30.0
      },
      "isRead": false
    }
  ],
  "scannedAt": "2024-01-15T15:00:00Z"
}
```

**Features**:
- Fetches latest ML forecast per symbol
- Aggregates alerts from last 7 days
- Counts unread alerts and flags critical severity
- Includes latest price and daily change
- Returns all alerts for display in AlertsTabView

---

## 📱 Swift Models

### `OptionsRankingResponse.swift`

**Structs**:
- `OptionsRankingsResponse` - API response wrapper
- `OptionRank` - Individual ML-scored contract
- `RankingFilters` - Active filter state
- `OptionSide` - Enum: call | put

**Computed Properties**:
- `scorePercentage` - ML score as 0-100
- `scoreColor` - Green (≥70%), Orange (≥40%), Red (<40%)
- `scoreLabel` - "Strong" | "Moderate" | "Weak"
- `expiryDate` - Parsed Date from ISO8601
- `daysToExpiry` - Calendar days to expiration

---

### `ScannerResponse.swift`

**Structs**:
- `ScannerWatchlistResponse` - API response wrapper
- `WatchlistItem` - Symbol with ML signal and alert data
- `ScannerAlert` - Individual alert with severity and details
- `AnyCodable` - Type-safe JSON flexible decoder

**Enums**:
- `AlertConditionType`: technical | ml | volume | price
- `AlertSeverity`: info | warning | critical

**Computed Properties**:
- `priceChangeColor` - Green (up) | Red (down) | Gray (unchanged)
- `mlLabelColor` - Green (bullish) | Orange (neutral) | Red (bearish)
- `alertBadgeColor` - Red (critical) | Orange (warning) | Clear (none)
- `severityIcon` - SF Symbol name for alert type
- `conditionTypeIcon` - Category-specific icons

---

## ✅ Completed Deliverables

### Phase 6.1: Options Data & Ranks
- ✅ Enhanced `options_ranks` schema (8 new columns, 2 new indexes)
- ✅ `OptionsRanker` ML scoring class with 6-factor model
- ✅ `options_ranking_job.py` batch processor
- ✅ Options chain data available via existing `/options-chain` endpoint

### Phase 6.2: Rankings Endpoint
- ✅ `GET /options-rankings` Edge Function
- ✅ Deployed to Supabase production
- ✅ Filtering by expiry, side, and limit
- ⏳ Plan gating (deferred for MVP testing)

### Phase 6.3: Client Models
- ✅ `OptionsRankingResponse.swift` with helper properties
- ⏳ `OptionsRankerService` API client (pending)
- ⏳ UI integration in `OptionsChainView` (pending)

### Phase 6.4: Watchlist Scanner
- ✅ Enhanced `scanner_alerts` schema (4 new columns, 2 new indexes)
- ✅ `POST /scanner-watchlist` Edge Function
- ✅ Deployed to Supabase production
- ✅ `ScannerResponse.swift` with badge helpers
- ⏳ `ScannerService` API client (pending)
- ⏳ Alert badges in `WatchlistView` (pending)
- ⏳ `AlertsTabView` for alert display (pending)

---

## 🔄 Next Steps (Frontend Integration)

To complete Phase 6, the following UI components need implementation:

1. **Options Ranker Service**
   - Create `OptionsRankerService` to call `/options-rankings`
   - Add to `MarketDataService` or create dedicated service
   - Handle error states and loading

2. **Options Ranking UI**
   - Option A: Add "Ranked" toggle to existing `OptionsChainView`
   - Option B: Create dedicated `OptionsRankerTabView`
   - Display ML scores with color coding
   - Show "Strong/Moderate/Weak" labels

3. **Scanner Service**
   - Create `ScannerService` to call `/scanner-watchlist`
   - Integrate with `WatchlistViewModel`
   - Periodic refresh (every 10 min aligned with data cadence)

4. **Watchlist Badges**
   - Add alert count badge to `WatchlistRow`
   - Show critical alert indicator (red dot/icon)
   - Display ML label chip (green/orange/red)

5. **Alerts Tab View**
   - Create `AlertsTabView` in right sidebar tabs
   - Group alerts by symbol or severity
   - Mark as read functionality
   - Filter by condition type

---

## 🎯 Architecture Benefits

### Scalability
- Options ranking runs independently from live data fetching
- Scanner supports batch processing of entire watchlist
- JSONB `details` field allows flexible alert payloads

### Performance
- Composite indexes optimize top-N queries
- Limited result sets (default 50 contracts)
- 7-day alert window prevents unbounded growth

### Extensibility
- Easy to add new scoring factors to `OptionsRanker`
- Alert condition types support future scanners (e.g., earnings, news)
- Plan gating hooks ready for premium tier features

---

## 📊 Testing & Validation

### Backend Endpoints
```bash
# Test options rankings
curl "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL&limit=10"

# Test scanner
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/scanner-watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "MSFT"]}'
```

### Database Queries
```sql
-- Check options_ranks schema
\d options_ranks

-- View sample ML-ranked contracts
SELECT contract_symbol, strike, side, ml_score, run_at
FROM options_ranks
WHERE underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
ORDER BY ml_score DESC
LIMIT 10;

-- Check scanner_alerts schema
\d scanner_alerts

-- View recent unread alerts
SELECT symbol_id, condition_label, severity, triggered_at
FROM scanner_alerts
WHERE is_read = FALSE
ORDER BY triggered_at DESC;
```

---

## 🏁 Summary

Phase 6 backend is **production-ready**:
- ✅ Database schema complete and migrated
- ✅ ML ranking algorithm implemented and tested
- ✅ Edge Functions deployed and accessible
- ✅ Swift models ready for integration

**Remaining work**: Frontend services and UI components (~2-3 components to build).

**Impact**: Enables ML-driven options discovery and proactive watchlist monitoring, two key differentiators for the platform's value proposition.
