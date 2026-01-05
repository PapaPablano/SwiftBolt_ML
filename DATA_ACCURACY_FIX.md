# Data Accuracy Fix - January 5, 2026

## Problem Identified

All historical stock price data was **corrupted due to split/dividend adjustments** being applied by the Polygon API. This caused significant discrepancies between stored data and actual historical trading prices:

- **NVDA**: Up to 15.91% price difference (e.g., showing $186 instead of actual $202)
- **AAPL**: 1-3% systematic price inflation in recent data
- **Root Cause**: `adjusted=true` parameter in Polygon API calls

## What Was Wrong

When `adjusted=true`, Polygon retroactively adjusts all historical prices whenever a stock split or dividend occurs. This means:
- Historical prices don't match what actually traded
- Prices change retroactively when new splits/dividends occur
- Charts and analysis show incorrect historical values

## Fix Applied

### Code Changes

Changed `adjusted=true` to `adjusted=false` in three locations:

1. **`backend/supabase/functions/_shared/providers/massive-client.ts:256`**
   - Main data provider for real-time and historical data
   
2. **`backend/supabase/functions/symbol-backfill/index.ts:74`**
   - Deep backfill function for historical data
   
3. **`backend/supabase/functions/_shared/massive-client.ts:98`**
   - Legacy massive-client implementation

### Database Migration

Added `backend/supabase/migrations/20260105120000_add_price_adjustment_tracking.sql`:
- New column `is_adjusted` to track adjustment status
- Index for efficient querying
- Marks existing data as adjusted (corrupted)

## How to Fix Your Data

### Option 1: Automated Re-fetch (Recommended)

Run the provided script to purge and re-fetch all data:

```bash
cd /Users/ericpeterson/SwiftBolt_ML
./purge_and_refetch_data.sh
```

**Warning**: This will delete ALL existing OHLC data and re-fetch from Polygon. Estimated time: 1-2 hours depending on number of symbols.

### Option 2: Manual Re-fetch for Specific Symbols

Re-fetch individual symbols using the backfill function:

```bash
# Example: Re-fetch NVDA
curl -X POST "$SUPABASE_URL/functions/v1/symbol-backfill" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "NVDA", "timeframes": ["d1", "h1", "m15"], "force": true}'
```

### Option 3: Verify Before Re-fetching

Check which symbols have the most corruption:

```bash
python3 verify_price_accuracy.py
```

This will compare your CSV data against Yahoo Finance and report discrepancies.

## Verification

After re-fetching data, verify accuracy:

1. **Run validation script**:
   ```bash
   python3 verify_price_accuracy.py
   ```

2. **Check specific dates**:
   ```bash
   python3 check_nvda_prices.py  # Check NVDA October 2025
   ```

3. **Compare against charts**: Verify prices match TradingView/Yahoo Finance

## Expected Results

After fix:
- ✅ Prices match actual historical trading prices
- ✅ Data matches what you see on charts
- ✅ No retroactive changes when splits/dividends occur
- ✅ Accurate for backtesting and analysis

## Trade-offs

### Using Unadjusted Prices (Current Fix)

**Pros:**
- Matches actual historical trading prices
- Consistent with real-time charts
- No retroactive changes
- Accurate for short-term analysis

**Cons:**
- Need to manually handle stock splits for long-term analysis
- Prices not comparable across split events
- Volume may appear artificially high/low after splits

### Alternative: Keep Adjusted Prices

If you prefer adjusted prices for long-term trend analysis:
1. Change `adjusted=false` back to `adjusted=true`
2. Document that prices are adjusted
3. Use only for analysis, not for matching real-time prices

## Files Changed

- ✅ `backend/supabase/functions/_shared/providers/massive-client.ts`
- ✅ `backend/supabase/functions/symbol-backfill/index.ts`
- ✅ `backend/supabase/functions/_shared/massive-client.ts` (legacy)
- ✅ `backend/supabase/migrations/20260105120000_add_price_adjustment_tracking.sql`
- ✅ `purge_and_refetch_data.sh` (new)
- ✅ `verify_price_accuracy.py` (validation tool)

## Next Steps

1. **Deploy the code changes** to your Supabase functions
2. **Run the migration** to add the `is_adjusted` column
3. **Execute purge_and_refetch_data.sh** to get clean data
4. **Verify accuracy** using the validation scripts
5. **Re-export CSV files** for any symbols you've exported previously

## Support

If you encounter issues:
1. Check Polygon API rate limits (5 req/min on free tier)
2. Verify `MASSIVE_API_KEY` is set correctly
3. Check Supabase function logs for errors
4. Run validation scripts to identify specific problem symbols

## References

- Polygon API Docs: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to
- `adjusted` parameter: Controls split/dividend adjustment
- Yahoo Finance: Used for validation (provides unadjusted prices)
