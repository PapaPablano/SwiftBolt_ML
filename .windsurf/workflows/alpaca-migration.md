---
description: Migrate all data providers to Alpaca-only
---

# Alpaca-Only Migration Workflow

## Overview
Consolidate all historical and intraday data fetching to Alpaca API, removing Polygon/Massive dependency.

## Benefits
- ✅ Single data source for all timeframes (m15, h1, h4, d1, w1)
- ✅ Cost savings: ~$150/month (cancel Polygon subscription)
- ✅ Simplified codebase: Remove provider routing complexity
- ✅ No provider label confusion: All data marked as 'alpaca'
- ✅ Better historical coverage: 7+ years from Alpaca

## Migration Steps

### 1. Python Backfill Scripts
**Files to update:**
- `ml/src/scripts/deep_backfill_ohlc_v2.py`
- `ml/src/scripts/process_backfill_queue.py`
- `ml/src/scripts/deep_backfill_ohlc.py`
- `ml/src/scripts/backfill_ohlc.py`

**Changes:**
- Replace Polygon API calls with Alpaca API
- Update provider label from 'polygon'/'massive' to 'alpaca'
- Use Alpaca authentication (ALPACA_API_KEY, ALPACA_API_SECRET)
- Update rate limiting (Alpaca: 200 req/min vs Polygon: 5 req/min)

### 2. Edge Functions Provider Router
**Files to update:**
- `supabase/functions/_shared/providers/factory.ts`
- `supabase/functions/_shared/providers/router.ts`

**Changes:**
- Remove Massive/Polygon client initialization
- Simplify router policy to use Alpaca-only (no fallbacks)
- Remove health check and fallback logic
- Keep Yahoo for options chain (Alpaca doesn't provide options)

### 3. Database Schema
**Create migration:**
- `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`

**Changes:**
- Update provider constraint to deprecate 'polygon' and 'massive'
- Simplify validation trigger (remove Polygon rules)
- Update get_chart_data_v2 to remove provider priority logic
- Add comment documenting Alpaca-only strategy

### 4. SQL Helper Functions
**Functions to update:**
- `get_chart_data_v2`: Remove DISTINCT ON provider priority
- `validate_ohlc_v2_write`: Remove Polygon validation rules
- Any other functions with provider-specific logic

### 5. Remove Dead Code
**Files to remove:**
- `supabase/functions/_shared/providers/massive-client.ts`
- Any Polygon-specific configuration files

**Files to clean:**
- Remove MASSIVE_API_KEY references
- Remove Polygon rate limit configurations

### 6. Environment Variables
**Update:**
- Remove `MASSIVE_API_KEY` / `POLYGON_API_KEY` from:
  - GitHub Actions secrets
  - Local .env files
  - Supabase Edge Function secrets
  - CI/CD pipelines

**Ensure set:**
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`

### 7. Testing Checklist
- [ ] Historical data fetch (d1, w1) works via Alpaca
- [ ] Intraday data fetch (m15, h1, h4) works via Alpaca
- [ ] Chart rendering shows correct provider labels
- [ ] No provider priority conflicts in database
- [ ] Backfill scripts successfully populate data
- [ ] Rate limiting works correctly (200 req/min)
- [ ] No references to Polygon/Massive in logs

### 8. Rollback Plan
If issues arise:
1. Revert database migration
2. Re-enable Polygon client in factory.ts
3. Restore MASSIVE_API_KEY environment variable
4. Revert Python script changes

## Post-Migration
1. Monitor Alpaca API usage and rate limits
2. Verify data quality matches Polygon
3. Cancel Polygon subscription after 1 week of stable operation
4. Update documentation to reflect Alpaca-only architecture

## Notes
- Keep Yahoo Finance client for options chain data
- Keep Tradier client for real-time intraday (if needed as backup)
- Alpaca provides both historical and real-time data
- No data migration needed - let old Polygon data age out naturally
