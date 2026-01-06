# Supabase Usage Audit & Recommendations

## Executive Summary

Based on Perplexity's review of our Supabase usage across Python, TypeScript, and Swift:

**Critical Issues Found:**
1. ❌ Using `.insert()` instead of `.upsert()` causing duplicate bars
2. ❌ Missing unique constraints on `(symbol_id, timestamp, timeframe)`
3. ❌ Edge Functions using anon key instead of service role key
4. ⚠️ No retry logic for transient failures
5. ⚠️ Inconsistent timezone handling across SDKs

**Impact:** These issues directly cause the chart rendering problems (duplicate bars, discontinuities).

---

## 1. Bulk Insert Anti-Pattern (CRITICAL)

### Current Issue
```python
# ❌ WRONG - Creates duplicates on retries
supabase.table('ohlc_bars_v2').insert(data).execute()
```

### Root Cause
- No unique constraint enforcement
- Retries/overlapping jobs create duplicate bars
- This is why you have 2-3 bars per day with different timestamps

### Fix Required
```python
# ✅ CORRECT - Idempotent upserts
supabase.table('ohlc_bars_v2').upsert(
    data, 
    on_conflict='symbol_id,ts,timeframe'
).execute()
```

### Database Migration Needed
```sql
-- Add unique constraint to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_unique 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider)
WHERE is_forecast = false;

-- For forecast data (can have multiple predictions)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_forecast_unique 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider)
WHERE is_forecast = true;
```

**Action:** Update all Python ingestion scripts to use `.upsert()`

---

## 2. Edge Function Authentication (CRITICAL)

### Current Issue
```typescript
// ❌ WRONG - Anon key enforces RLS unnecessarily
const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

### Impact
- RLS policies block legitimate writes
- Causes stale data issues
- 401 errors in production

### Fix Required
```typescript
// ✅ CORRECT - Service role bypasses RLS for admin ops
const supabase = createClient(
  supabaseUrl, 
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  { auth: { persistSession: false } }
)
```

**Action:** Update all Edge Functions to use service role key

---

## 3. Missing Error Handling & Retries

### Current Pattern
```python
# ❌ No retry logic
response = supabase.rpc('get_chart_data_v2', params).execute()
```

### Recommended Pattern
```python
# ✅ Exponential backoff retries
def safe_rpc(supabase, name, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            return supabase.rpc(name, params).execute()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt * 0.1)  # 100ms, 200ms, 400ms
    return None
```

**Action:** Wrap all Supabase calls with retry logic

---

## 4. Query Performance Issues

### Current Pattern
```python
# ⚠️ Multiple .eq() filters without indexes
supabase.table('ohlc_bars_v2') \
    .select('*') \
    .eq('symbol_id', id) \
    .eq('timeframe', 'd1') \
    .eq('provider', 'polygon') \
    .execute()
```

### Optimization
```sql
-- Add composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ohlc_query 
ON ohlc_bars_v2 (symbol_id, timeframe, provider, ts);

CREATE INDEX IF NOT EXISTS idx_ohlc_date_range 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_forecast = false;
```

**Action:** Add indexes for all common query patterns

---

## 5. Timezone Handling Inconsistencies

### Current Issues
- Python: Mixed timezone awareness
- TypeScript: Assumes UTC but doesn't enforce
- Swift: ISO8601 parsing without explicit UTC

### Standardized Approach

**Database:**
```sql
-- Note: ohlc_bars_v2.ts is currently TIMESTAMP (without time zone)
-- This is acceptable if all data is stored in UTC
-- Function parameters should use TIMESTAMPTZ to match Edge Function calls

-- If you want to convert the column (optional):
-- ALTER TABLE ohlc_bars_v2 ALTER COLUMN ts TYPE timestamptz USING ts AT TIME ZONE 'UTC';
```

**Important:** The `get_chart_data_v2` function now uses `TIMESTAMPTZ` parameters to match:
- Edge Function calls using `new Date().toISOString()`
- PostgreSQL `NOW()` function (returns `TIMESTAMPTZ`)
- Python datetime with timezone awareness

The function handles the comparison between `TIMESTAMPTZ` parameters and `TIMESTAMP` column correctly.

**Python:**
```python
from datetime import datetime, timezone

# ✅ Always use UTC
timestamp = datetime.now(timezone.utc)
iso_string = timestamp.isoformat()
```

**TypeScript:**
```typescript
// ✅ Explicit UTC
const timestamp = new Date().toISOString(); // Always UTC
```

**Swift:**
```swift
// ✅ Explicit UTC timezone
let formatter = ISO8601DateFormatter()
formatter.timeZone = TimeZone(secondsFromGMT: 0)!
let timestamp = formatter.string(from: Date())
```

---

## 6. Swift Client 401 Errors

### Root Cause
- Anon key is correct for client-side
- Missing RLS policies on tables
- Token expiry not handled

### Fix Required

**1. Enable RLS on all tables:**
```sql
ALTER TABLE ohlc_bars_v2 ENABLE ROW LEVEL SECURITY;

-- Allow public read access to verified data
CREATE POLICY "Public read access to verified bars"
ON ohlc_bars_v2 FOR SELECT
USING (data_status = 'verified');
```

**2. Handle token refresh in Swift:**
```swift
// Add to APIClient
func refreshSessionIfNeeded() async throws {
    if let session = try? await supabase.auth.session {
        if session.expiresAt < Date().timeIntervalSince1970 {
            try await supabase.auth.refreshSession()
        }
    }
}
```

---

## 7. RPC Parameter Naming Consistency

### Current Issue
- Function name: `chart-data-v2` (Edge Function)
- RPC name: `get_chart_data_v2` (PostgreSQL)
- Inconsistent parameter names

### Standardization
```typescript
// Edge Function wrapper
export async function handler(req: Request) {
  const { symbol, days, includeForecast } = await req.json();
  
  // Call PostgreSQL RPC with consistent naming
  const { data, error } = await supabase.rpc('get_chart_data_v2', {
    p_symbol_id: symbolId,      // Prefix 'p_' for parameters
    p_timeframe: timeframe,
    p_start_date: startDate,
    p_end_date: endDate
  });
}
```

---

## Implementation Priority

### Phase 1: Critical Fixes (Do Now)
1. ✅ Add unique constraints to prevent duplicates
2. ✅ Update Edge Functions to use service role key
3. ✅ Change all `.insert()` to `.upsert()` in Python
4. ✅ Apply deduplication SQL migration

### Phase 2: Reliability (This Week)
5. Add retry logic to all Supabase calls
6. Implement proper error handling
7. Add RLS policies for Swift client
8. Standardize timezone handling

### Phase 3: Performance (Next Week)
9. Add composite indexes for query optimization
10. Implement pagination for large result sets
11. Add caching layer for frequently accessed data

---

## Files Requiring Updates

### Python Scripts
- `ml/src/scripts/deep_backfill_ohlc_v2.py` - Change to `.upsert()`
- `ml/src/scripts/process_backfill_queue.py` - Change to `.upsert()`
- All data ingestion jobs - Add retry logic

### TypeScript Edge Functions
- `backend/supabase/functions/chart-data-v2/index.ts` - Use service role key
- All Edge Functions - Add retry wrapper

### Swift Client
- `client-macos/SwiftBoltML/Services/APIClient.swift` - Add session refresh
- Add RLS policy handling

### Database Migrations
- `20260105210000_add_unique_constraints.sql` - NEW
- `20260105220000_add_query_indexes.sql` - NEW
- `20260105230000_enable_rls_policies.sql` - NEW

---

## Testing Checklist

After implementing fixes:

- [ ] Verify no duplicate bars in database
- [ ] Test chart rendering with NVDA and AAPL
- [ ] Verify Edge Functions return fresh data
- [ ] Test Swift client doesn't get 401 errors
- [ ] Verify retry logic handles transient failures
- [ ] Check query performance with EXPLAIN ANALYZE
- [ ] Test timezone consistency across all SDKs

---

## Security Considerations

**Current State:**
- ✅ Service keys stored in environment variables
- ✅ Anon key used appropriately in Swift client
- ❌ Missing RLS policies on tables
- ❌ No rate limiting on Edge Functions

**Recommendations:**
1. Enable RLS on all tables
2. Add rate limiting to Edge Functions
3. Rotate keys quarterly
4. Implement audit logging for service role operations
5. Use Supabase Vault for sensitive credentials

---

## Performance Benchmarks

**Before Optimizations:**
- Chart data query: ~2-3 seconds (760 bars)
- Duplicate bars: 246 dates affected
- Edge Function cold start: ~500ms

**Expected After Optimizations:**
- Chart data query: <500ms (with indexes)
- Duplicate bars: 0 (with unique constraints)
- Edge Function cold start: ~300ms (with service role key)

---

## References

- [Supabase Python Client](https://github.com/supabase/supabase-py)
- [Supabase JS Client](https://github.com/supabase/supabase-js)
- [Supabase Swift Client](https://github.com/supabase/supabase-swift)
- [Supabase Best Practices](https://supabase.com/docs/guides/database/best-practices)
