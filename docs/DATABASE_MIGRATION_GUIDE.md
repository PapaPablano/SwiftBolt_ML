# Database Migration Guide - Entry/Exit Rankings
## January 23, 2026

## 📋 Overview

This migration adds support for entry and exit ranking modes by adding new columns to the `options_ranks` table.

**Migration File**: `supabase/migrations/20260123_add_entry_exit_rankings.sql`  
**Rollback File**: `supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql`  
**Impact**: Adds 10 new columns + 5 indexes to `options_ranks` table  
**Downtime**: None (columns are nullable, backward compatible)  

---

## 🗄️ Schema Changes

### New Columns Added

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `ranking_mode` | TEXT | NO | Mode: 'entry', 'exit', or 'monitor' (default) |
| `entry_rank` | NUMERIC | YES | Entry-optimized rank 0-100 |
| `exit_rank` | NUMERIC | YES | Exit-optimized rank 0-100 |
| `entry_value_score` | NUMERIC | YES | Entry value component (IV percentile, discount, spread) |
| `catalyst_score` | NUMERIC | YES | Catalyst component (price, volume surge, OI build) |
| `iv_percentile` | NUMERIC | YES | IV percentile (0-100) |
| `iv_discount_score` | NUMERIC | YES | IV discount vs historical |
| `profit_protection_score` | NUMERIC | YES | Profit component (P&L%, IV expansion, target) |
| `deterioration_score` | NUMERIC | YES | Deterioration component (momentum, volume, OI) |
| `time_urgency_score` | NUMERIC | YES | Time component (DTE urgency, theta burn) |

### New Indexes

```sql
idx_options_ranks_entry_rank              -- For sorting by entry_rank DESC
idx_options_ranks_exit_rank               -- For sorting by exit_rank DESC
idx_options_ranks_ranking_mode            -- For filtering by mode
idx_options_ranks_symbol_mode_entry       -- Composite: symbol + entry mode + rank
idx_options_ranks_symbol_mode_exit        -- Composite: symbol + exit mode + rank
```

### Constraints

```sql
CHECK (ranking_mode IN ('entry', 'exit', 'monitor'))
```

---

## 🚀 Migration Steps

### Option A: Automated (Recommended)

```bash
# Run the migration script
./scripts/run_migration.sh
```

The script will:
1. Show dry-run preview
2. Ask for confirmation
3. Apply migration
4. Run verification
5. Display next steps

### Option B: Supabase Dashboard (Manual)

1. Go to your Supabase project dashboard
2. Navigate to: **SQL Editor**
3. Create new query
4. Copy contents of `supabase/migrations/20260123_add_entry_exit_rankings.sql`
5. Click **Run**
6. Verify success message: "Migration successful: All 8 columns added"

### Option C: Command Line (psql)

```bash
# Set your database URL
export DATABASE_URL="postgresql://..."

# Apply migration
psql $DATABASE_URL -f supabase/migrations/20260123_add_entry_exit_rankings.sql

# Verify migration
psql $DATABASE_URL -f scripts/verify_ranking_migration.sql
```

---

## ✅ Verification

### Quick Check

```sql
-- Verify columns exist
SELECT column_name, data_type 
FROM information_schema.columns
WHERE table_name = 'options_ranks'
AND column_name IN ('entry_rank', 'exit_rank', 'ranking_mode');
```

Expected output: 3 rows

### Full Verification

```bash
# Run verification script
psql $DATABASE_URL -f scripts/verify_ranking_migration.sql
```

Should show:
- ✅ 10 new columns
- ✅ 5 new indexes
- ✅ 1 CHECK constraint
- ✅ Column comments

---

## 📊 Testing with Sample Data

### 1. Insert Test Entry Mode Ranking

```sql
INSERT INTO options_ranks (
    underlying_symbol_id,
    contract_symbol,
    strike,
    side,
    expiry,
    ranking_mode,
    entry_rank,
    entry_value_score,
    catalyst_score,
    greeks_score,
    composite_rank,
    momentum_score,
    value_score,
    run_at
)
SELECT 
    (SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1),
    'AAPL_TEST_180_C',
    180,
    'call',
    CURRENT_DATE + INTERVAL '30 days',
    'entry',
    75.7,
    77.0,
    75.5,
    74.0,
    72.5,  -- Also populate monitor fields for comparison
    78.3,
    64.9,
    NOW();
```

### 2. Query Entry Rankings

```sql
SELECT 
    contract_symbol,
    strike,
    side,
    ranking_mode,
    entry_rank,
    entry_value_score,
    catalyst_score
FROM options_ranks
WHERE ranking_mode = 'entry'
AND underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
ORDER BY entry_rank DESC
LIMIT 5;
```

### 3. Compare Across Modes

```sql
SELECT 
    contract_symbol,
    ranking_mode,
    CASE ranking_mode
        WHEN 'entry' THEN entry_rank
        WHEN 'exit' THEN exit_rank
        ELSE composite_rank
    END as rank
FROM options_ranks
WHERE contract_symbol = 'AAPL_TEST_180_C'
ORDER BY ranking_mode;
```

---

## 🔄 Data Migration (Existing Records)

Existing records will have:
- `ranking_mode = 'monitor'` (default)
- `entry_rank = NULL`
- `exit_rank = NULL`
- `composite_rank` remains populated

**No data loss** - all existing rankings continue to work.

### Populate Entry/Exit Ranks for Existing Records

After migration, run the Python ranking job:

```bash
cd ml

# Rank in ENTRY mode
python -m src.options_ranking_job \
    --symbol AAPL \
    --mode entry \
    --save-to-db

# Rank in EXIT mode (for contracts you own)
python -m src.options_ranking_job \
    --symbol AAPL \
    --mode exit \
    --entry-price 2.50 \
    --save-to-db

# Continue with MONITOR mode (backward compatible)
python -m src.options_ranking_job \
    --symbol AAPL \
    --mode monitor \
    --save-to-db
```

---

## 🔙 Rollback Instructions

If you need to revert the migration:

```bash
# Using Supabase Dashboard
# 1. Go to SQL Editor
# 2. Run: supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql

# Or via command line
psql $DATABASE_URL -f supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql
```

**⚠️ Warning**: Rollback will **delete all entry/exit ranking data**. Make sure to backup first if needed.

---

## 📈 Expected Database Size Impact

### Before Migration
- `options_ranks` table: ~500KB per 1000 rows (existing columns)

### After Migration
- Added columns: ~100KB per 1000 rows (10 NUMERIC columns)
- Added indexes: ~150KB per 1000 rows (5 indexes)
- **Total increase**: ~250KB per 1000 rows (~25% increase)

For 100,000 rankings: **~25MB increase**

---

## 🔍 Monitoring & Validation

### Check Migration Status

```sql
-- Count records by mode
SELECT 
    ranking_mode,
    COUNT(*) as total,
    COUNT(entry_rank) as with_entry,
    COUNT(exit_rank) as with_exit,
    COUNT(composite_rank) as with_monitor
FROM options_ranks
GROUP BY ranking_mode;
```

Expected after Python jobs run:
```
ranking_mode | total | with_entry | with_exit | with_monitor
-------------|-------|------------|-----------|-------------
entry        | 50    | 50         | 0         | 50
exit         | 50    | 0          | 50        | 50
monitor      | 50    | 0          | 0         | 50
```

### Check Index Usage

```sql
-- Verify indexes are being used
EXPLAIN ANALYZE
SELECT * FROM options_ranks
WHERE ranking_mode = 'entry'
AND underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
ORDER BY entry_rank DESC
LIMIT 20;
```

Should show: `Index Scan using idx_options_ranks_symbol_mode_entry`

---

## 🚨 Troubleshooting

### Issue: Migration fails with "column already exists"

**Solution**: Columns already added. Run verification to confirm:
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'options_ranks' AND column_name = 'entry_rank';
```

### Issue: Constraint violation on ranking_mode

**Solution**: Ensure `ranking_mode` is one of: 'entry', 'exit', 'monitor'
```sql
-- Check invalid values
SELECT ranking_mode, COUNT(*) 
FROM options_ranks 
WHERE ranking_mode NOT IN ('entry', 'exit', 'monitor')
GROUP BY ranking_mode;
```

### Issue: Rankings are NULL

**Solution**: Python job hasn't run yet. Rankings are populated by:
```bash
python -m src.options_ranking_job --symbol AAPL --mode entry
```

### Issue: Slow queries after migration

**Solution**: Run ANALYZE to update statistics:
```sql
ANALYZE options_ranks;
```

---

## 📋 Post-Migration Checklist

- [ ] Migration applied successfully
- [ ] Verification script shows 10 columns + 5 indexes
- [ ] Test entry ranking inserted and queryable
- [ ] Python ranking job runs for entry mode
- [ ] Python ranking job runs for exit mode
- [ ] API endpoint returns entry_rank/exit_rank fields
- [ ] Frontend displays mode-specific ranks
- [ ] No performance degradation on queries
- [ ] Backup created (if in production)

---

## 📞 Support

**Issues?**
1. Check verification output: `psql $DATABASE_URL -f scripts/verify_ranking_migration.sql`
2. Review migration log in Supabase Dashboard → Database → Logs
3. Run rollback if critical issue: `...rollback.sql`
4. Re-apply migration after fixing

**Success Criteria**:
- ✅ All columns exist
- ✅ All indexes created
- ✅ No errors in logs
- ✅ Sample query returns results
- ✅ API accepts mode parameter

---

## 🎯 Next Steps After Migration

1. **Update Python Job** (`src/options_ranking_job.py`):
   - Add mode parameter
   - Save entry_rank, exit_rank, component scores

2. **Test Backend API**:
   ```bash
   curl "https://YOUR_PROJECT.supabase.co/functions/v1/options-rankings?symbol=AAPL&mode=entry"
   ```

3. **Deploy Frontend UI**:
   - Add mode selector
   - Display mode-specific ranks
   - Update Contract Workbench

4. **Monitor Performance**:
   - Check query execution times
   - Monitor index usage
   - Track database size

---

## ✅ Migration Complete!

Your database is now ready for entry/exit ranking modes! 🚀

**Backup Location**: Supabase automatic backups (if enabled)  
**Migration Duration**: ~5-10 seconds  
**Rollback Available**: Yes (`...rollback.sql`)  
**Breaking Changes**: None (backward compatible)
