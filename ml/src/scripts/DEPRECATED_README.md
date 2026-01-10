# Deprecated Scripts

**Date**: 2026-01-10  
**Reason**: Migration to Alpaca-only data strategy

## ⚠️ These scripts use deprecated providers and should not be used

### Deprecated Scripts

1. **`backfill_ohlc_yfinance.py`**
   - Provider: Yahoo Finance
   - Status: ❌ DEPRECATED
   - Replacement: Use `scripts/backfill_missing_data.sh` (Alpaca-based)
   - Issue: Writes data with `provider='yfinance'` which conflicts with Alpaca data

2. **`backfill_ohlc.py`**
   - Provider: Polygon (via Massive API)
   - Status: ❌ DEPRECATED
   - Replacement: Use Alpaca API directly
   - Issue: Writes data with `provider='massive'`

## Why Deprecated?

As of 2026-01-10, the database enforces an **Alpaca-only strategy** for OHLCV data:
- All new OHLCV bars MUST use `provider='alpaca'`
- Legacy providers (yfinance, polygon, tradier) are READ-ONLY
- Database trigger will reject writes from deprecated providers

## What to Use Instead

### For Historical Backfills
```bash
# Use the Alpaca-based backfill script
cd /Users/ericpeterson/SwiftBolt_ML
./scripts/backfill_missing_data.sh
```

### For Real-time Data
The `chart-data-v2` edge function automatically fetches from Alpaca.

### For Options Data
Tradier is still the primary provider for options chains (not OHLCV).
Continue using `tradier_client.py` for options-related queries.

## Migration Guide

If you need to backfill data:

1. **Don't use these scripts** - they will fail or create conflicts
2. **Use the Alpaca backfill script** at `scripts/backfill_missing_data.sh`
3. **Or call chart-data-v2** edge function which uses Alpaca

## References

- Migration SQL: `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`
- Audit doc: `docs/DEPRECATED_PROVIDERS_AUDIT.md`
- Alpaca docs: https://alpaca.markets/docs/
