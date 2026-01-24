# Legacy Scripts

**Archived**: 2026-01-21

This directory contains legacy scripts that have been superseded by the canonical scripts in `../canonical/`.

## Why Archived

These scripts were created during development and debugging. They contain:
- Duplicate functionality
- Ad-hoc fixes that are now integrated into canonical scripts
- Debugging/diagnostic scripts no longer needed

## Canonical Replacements

| Legacy Script | Replaced By |
|--------------|-------------|
| `simple-backfill-trigger.sh` | `canonical/backfill.sh` |
| `reload_watchlist_alpaca.sh` | `canonical/backfill.sh` |
| `trigger-alpaca-backfill.sql` | `canonical/backfill.sh` |
| `fix-intraday-data.sh` | `canonical/backfill.sh` |
| `deploy-internal-functions.sh` | `canonical/deploy.sh` |
| `deploy-phase2-batch.sh` | `canonical/deploy.sh` |
| `deploy-backfill-updates.sh` | `canonical/deploy.sh` |
| `migrate-to-phase2-batch.sh` | `canonical/deploy.sh` |
| `validate-phase2.sql` | `canonical/validate.sh` |
| `check_data_ingestion.sql` | `canonical/validate.sh` |
| `diagnose-intraday-data.sql` | `canonical/validate.sh` |
| `diagnose_chart_data_issue.sql` | `canonical/validate.sh` |
| `verify_latest_available.sql` | `canonical/validate.sh` |
| `check_latest_prices.sql` | `canonical/validate.sh` |
| `seed-and-verify-symbols.sh` | `canonical/seed.sh` |

## Scripts in This Directory

### Shell Scripts (Debugging)
- `apply_fix_direct.sh` - One-time fix application
- `check-chart-provider.sh` - Provider debugging
- `check-chunk-range.sh` - Data chunk debugging
- `check-database-directly.sh` - Direct DB queries
- `cleanup-and-restart.sh` - Clean restart procedure
- `create-phase2-universe.sh` - Phase 2 universe setup
- `quick-fix.sh` - Quick fixes during development
- `reset-and-continue.sh` - Reset and continue debugging
- `show-alpaca-bars.sh` - Alpaca data inspection
- `test-phase2-batch.sh` - Phase 2 batch testing

### SQL Scripts (Diagnostic)
- `check_data_ingestion.sql` - Data ingestion checks
- `check_database_function.sql` - Function checks
- `check_latest_prices.sql` - Price freshness
- `clear_watchlist_chart_data.sql` - Chart data cleanup
- `diagnose-intraday-data.sql` - Intraday diagnostics
- `diagnose_chart_data_issue.sql` - Chart issue diagnosis
- `reset_watchlist_data.sql` - Watchlist reset
- `test_chart_query.sql` - Chart query testing
- `trigger-alpaca-backfill.sql` - Alpaca backfill trigger
- `validate-phase2.sql` - Phase 2 validation
- `verify_latest_available.sql` - Data availability check

### TypeScript Scripts
- `test_chart_query.ts` - Chart query testing
- `test_current_function.ts` - Function testing

### Documentation
- `APPLY_H1_FIX.md` - H1 fix instructions
- `MANUAL_RELOAD_STEPS.md` - Manual reload steps

## Usage

**Do not use these scripts directly.** Use the canonical scripts instead:

```bash
# Backfill data
../canonical/backfill.sh --symbol AAPL

# Deploy functions
../canonical/deploy.sh --functions

# Validate system
../canonical/validate.sh

# Seed database
../canonical/seed.sh
```

## Restoration

If you need to restore a legacy script for reference:

```bash
# View script content
cat legacy/script-name.sh

# Copy back (not recommended)
cp legacy/script-name.sh ../
```

Consider updating the canonical scripts instead of restoring legacy ones.
