# Futures Chain Implementation - Deployment Guide

## Summary

This implementation adds comprehensive futures reference data support to SwiftBolt ML, enabling TradingView-style contract discovery with:
- Full dated contract chains (e.g., GCZ25, GCF26, GCG26...)
- Continuous contract aliases (GC1!, GC2!, etc.)
- Automatic roll detection and mapping
- Massive (Polygon) API integration

## Files Created

### 1. Database Migration
**File:** `supabase/migrations/20260215010000_add_futures_chain_schema.sql`

**Tables Created:**
- `futures_roots` - Root symbols (ES, NQ, GC, etc.) with specs
- `futures_contracts` - Individual dated contracts
- `futures_roll_config` - Per-root roll configuration
- `futures_roll_events` - Historical roll events for reproducibility
- `futures_continuous_map` - Continuous alias → dated contract mapping

**Views Created:**
- `v_futures_chain` - Active contracts with continuous mapping
- `v_futures_front_month` - Current front month contracts

**Functions Created:**
- `generate_contract_symbol()` - Generate CME contract symbols
- `get_continuous_contract()` - Get current continuous mapping
- `resolve_futures_symbol()` - Resolve any symbol to contract details

**MVP Roots Seeded:**
- Indices: ES, NQ, RTY, YM, EMD
- Metals: GC, SI, HG

### 2. Edge Functions

#### `/futures-roots` (GET)
```bash
GET /futures/roots?sector=indices|metals
```
Returns list of futures roots with metadata.

**Response:**
```json
{
  "success": true,
  "count": 8,
  "roots": [{
    "id": "...",
    "symbol": "GC",
    "name": "Gold",
    "exchange": "COMEX",
    "sector": "metals",
    "tick_size": 0.1,
    "point_value": 100
  }]
}
```

#### `/futures-chain` (GET)
```bash
GET /futures/chain?root=GC&asOf=2026-02-15
```
Returns full contract chain for a root.

**Response:**
```json
{
  "success": true,
  "root": {
    "symbol": "GC",
    "name": "Gold",
    "exchange": "COMEX",
    "sector": "metals"
  },
  "as_of": "2026-02-15",
  "contracts": [{
    "id": "...",
    "symbol": "GCZ25",
    "contract_code": "Z25",
    "expiry_month": 12,
    "expiry_year": 2025,
    "last_trade_date": "2025-12-29",
    "is_active": true,
    "is_spot": true,
    "continuous_alias": "GC1!",
    "continuous_depth": 1
  }],
  "continuous_aliases": [{
    "alias": "GC1!",
    "depth": 1,
    "contract_symbol": "GCZ25"
  }]
}
```

#### `/futures-continuous` (GET)
```bash
GET /futures/continuous?root=GC&depth=1
```
Returns continuous contract mapping.

**Response:**
```json
{
  "success": true,
  "root": "GC",
  "depth": 1,
  "as_of": "2026-02-15",
  "contracts": [{
    "alias": "GC1!",
    "depth": 1,
    "contract": {
      "id": "...",
      "symbol": "GCZ25",
      "expiry_month": 12,
      "expiry_year": 2025,
      "last_trade_date": "2025-12-29",
      "days_to_expiry": 317
    },
    "valid_from": "2026-01-15",
    "valid_until": null
  }]
}
```

#### `/sync-futures-data` (POST)
```bash
POST /sync-futures-data
Content-Type: application/json

{
  "roots": ["GC", "ES"],  // Optional: specific roots
  "force": false          // Optional: force refresh
}
```
Syncs futures reference data from Massive API to database.

### 3. Provider Extensions

#### `types.ts`
Added futures types:
- `FuturesRoot` - Root symbol metadata
- `FuturesContract` - Dated contract details
- `FuturesChain` - Chain response structure
- `FuturesContinuousMapping` - Continuous mapping

#### `massive-client.ts`
Added methods:
- `getFuturesRoots(sector?)` - Fetch roots
- `getFuturesChain(root)` - Fetch full chain
- `getFuturesContract(symbol)` - Fetch single contract

## Deployment Steps

### 1. Apply Database Migration

```bash
# Deploy to Supabase
supabase db push

# Or run locally
psql $DATABASE_URL -f supabase/migrations/20260215010000_add_futures_chain_schema.sql
```

### 2. Deploy Edge Functions

```bash
# Deploy all new functions
supabase functions deploy futures-roots
supabase functions deploy futures-chain
supabase functions deploy futures-continuous
supabase functions deploy sync-futures-data

# Or deploy all at once
supabase functions deploy
```

### 3. Sync Initial Data

```bash
# Call the sync function to populate contracts
curl -X POST https://your-project.supabase.co/functions/v1/sync-futures-data \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 4. Set Up Cron Job (Optional)

Add to `supabase/config.toml` or via dashboard:

```toml
[functions.sync-futures-data]
schedule = "0 6 * * *"  # Daily at 6 AM
```

Or use SQL:
```sql
SELECT cron.schedule(
  'sync-futures-data-daily',
  '0 6 * * *',
  $$ SELECT net.http_post(
    url:='https://your-project.supabase.co/functions/v1/sync-futures-data',
    headers:='{"Authorization": "Bearer ' || current_setting('app.settings.service_role_key') || '"}'::jsonb
  ) $$
);
```

## API Usage Examples

### Get All Futures Roots
```bash
curl "https://your-project.supabase.co/functions/v1/futures-roots"
```

### Get Metals Roots Only
```bash
curl "https://your-project.supabase.co/functions/v1/futures-roots?sector=metals"
```

### Get Full Contract Chain for Gold
```bash
curl "https://your-project.supabase.co/functions/v1/futures-chain?root=GC"
```

### Get Continuous Contract Mapping
```bash
curl "https://your-project.supabase.co/functions/v1/futures-continuous?root=GC&depth=2"
```

## Integration with Chart Data

To use futures symbols in chart endpoints:

1. **Dated Contract:** Pass the full symbol (e.g., `GCZ25`)
2. **Continuous Contract:** Pass the alias (e.g., `GC1!`)

The chart endpoint will need to be extended to resolve these symbols using the `resolve_futures_symbol()` SQL function.

## Next Steps

1. **Extend Chart Endpoint:** Modify `chart-data-v2` to resolve futures symbols
2. **Add Roll Detection:** Implement volume/OI-based roll detection in sync job
3. **Back-adjustment:** Add additive/multiplicative adjustment modes
4. **Historical Data:** Ingest OHLC data for futures contracts
5. **Options on Futures:** Extend options chain support

## Testing

```bash
# Test roots endpoint
curl "http://localhost:54321/functions/v1/futures-roots" | jq

# Test chain endpoint
curl "http://localhost:54321/functions/v1/futures-chain?root=GC" | jq

# Test sync
curl -X POST "http://localhost:54321/functions/v1/sync-futures-data" \
  -H "Content-Type: application/json" \
  -d '{"roots": ["GC"]}' | jq
```

## Notes

- Roll detection is currently simple (based on contract generation)
- Volume/OI data needs to be populated via additional data feeds
- Margin requirements not included (broker-specific)
- Trading hours are simplified - use CME calendar API for production
