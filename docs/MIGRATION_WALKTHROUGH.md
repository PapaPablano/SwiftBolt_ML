# 🚀 Database Migration - Step-by-Step Walkthrough
## Entry/Exit Ranking System - January 23, 2026

---

## ✅ Pre-Flight Check

**Your Setup**:
- ✅ Supabase Project: `cygflaemtmwiwaviclks`
- ✅ Environment: **Production**
- ✅ Dashboard: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks
- ✅ Migration file ready: `supabase/migrations/20260123_add_entry_exit_rankings.sql`
- ✅ Rollback file ready: `supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql`

**What we're adding**:
- 10 new columns to `options_ranks` table
- 5 new indexes for performance
- All backward compatible (existing code continues to work)

**Estimated time**: 5-10 minutes

---

## 🎯 OPTION A: Supabase Dashboard (RECOMMENDED)

### Step 1: Open SQL Editor (1 minute)

1. **Go to**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql
2. **Click**: "New Query" button (top right)
3. **Name it**: "Add Entry/Exit Rankings" (optional)

### Step 2: Copy Migration SQL (1 minute)

1. **Open file**: `supabase/migrations/20260123_add_entry_exit_rankings.sql` (in your IDE)
2. **Copy all** (⌘+A, ⌘+C) - all 96 lines
3. **Paste** into the SQL Editor

### Step 3: Review the SQL (1 minute)

Scroll through and verify you see:
- ✅ `BEGIN;` at the top
- ✅ `ALTER TABLE options_ranks ADD COLUMN...` statements
- ✅ `CREATE INDEX...` statements
- ✅ `COMMIT;` at the bottom

### Step 4: Execute Migration (30 seconds)

1. **Click**: "Run" button (or press ⌘+Enter)
2. **Watch**: Output panel at bottom
3. **Look for**: 
   ```
   NOTICE: Migration successful: All 8 columns added to options_ranks
   ```

### Step 5: Verify Success (1 minute)

Create a new query and run:
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'options_ranks'
AND column_name IN (
    'ranking_mode', 'entry_rank', 'exit_rank',
    'entry_value_score', 'catalyst_score',
    'profit_protection_score', 'deterioration_score', 'time_urgency_score'
)
ORDER BY column_name;
```

**Expected output**: 8 rows

### Step 6: Test Query (1 minute)

Test that existing queries still work:
```sql
SELECT 
    contract_symbol,
    strike,
    side,
    composite_rank,
    ranking_mode,
    entry_rank,
    exit_rank
FROM options_ranks
WHERE underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1)
ORDER BY run_at DESC
LIMIT 5;
```

**Expected**: 
- ✅ Query runs successfully
- ✅ `composite_rank` has values (existing data)
- ✅ `ranking_mode` = 'monitor' (default)
- ✅ `entry_rank` and `exit_rank` are NULL (not populated yet - that's correct!)

---

## 🎯 OPTION B: Supabase CLI (Command Line)

### Step 1: Link to Remote Project (if not linked)

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Link to your project
supabase link --project-ref cygflaemtmwiwaviclks
```

### Step 2: Apply Migration

```bash
# Dry run first (see what will happen)
supabase db push --dry-run

# Apply migration
supabase db push
```

### Step 3: Verify

```bash
# Check migration status
supabase db remote status

# Run verification
psql "$(supabase db remote-url)" -f scripts/verify_ranking_migration.sql
```

---

## 🎯 OPTION C: Direct psql (Advanced)

```bash
# Get your database password from Supabase dashboard first
# Settings → Database → Connection string

# Apply migration
psql "postgresql://postgres:[PASSWORD]@db.cygflaemtmwiwaviclks.supabase.co:5432/postgres" \
     -f supabase/migrations/20260123_add_entry_exit_rankings.sql

# Verify
psql "postgresql://postgres:[PASSWORD]@db.cygflaemtmwiwaviclks.supabase.co:5432/postgres" \
     -f scripts/verify_ranking_migration.sql
```

---

## ✅ Success Indicators

After running the migration, you should see:

### ✅ In SQL Output
```
BEGIN
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE INDEX
COMMENT
COMMENT
... (more COMMENT statements)
NOTICE: Migration successful: All 8 columns added to options_ranks
COMMIT
```

### ✅ In Verification Query
- 8 new columns exist
- All are NUMERIC type (except ranking_mode which is TEXT)
- All are nullable (except ranking_mode)
- ranking_mode has default 'monitor'

### ✅ In Test Query
- Existing data still loads
- composite_rank still has values
- New columns are NULL (correct - not populated yet)

---

## ❌ Troubleshooting

### Error: "relation 'options_ranks' does not exist"

**Problem**: Table name might be different  
**Fix**: Check your actual table name:
```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
```

### Error: "column 'entry_rank' already exists"

**Problem**: Migration was already run  
**Fix**: Run verification instead:
```sql
SELECT column_name FROM information_schema.columns WHERE table_name = 'options_ranks';
```

### Error: "permission denied"

**Problem**: Using wrong credentials  
**Fix**: Make sure you're using a user with DDL permissions (postgres user or owner)

### Migration Succeeded but No NOTICE

**Not a problem**: The NOTICE is optional. Verify with:
```sql
SELECT COUNT(*) FROM information_schema.columns 
WHERE table_name = 'options_ranks' 
AND column_name = 'entry_rank';
```
Should return: 1

---

## 🔄 If You Need to Rollback

**Only if something goes wrong:**

```sql
-- In Supabase SQL Editor, run:
-- Copy/paste from: supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql
```

This will remove all changes safely.

---

## 📊 After Migration

### Immediate Next Steps

1. ✅ Migration complete
2. ⏭️ Run Python job to populate entry_rank/exit_rank
3. ⏭️ Test API with ?mode=entry parameter
4. ⏭️ Deploy frontend UI

### Data Status

**Before Python job runs**:
- `ranking_mode` = 'monitor' (all existing records)
- `entry_rank` = NULL
- `exit_rank` = NULL
- `composite_rank` = (existing values)

**After Python job runs** (next step):
- New records will have entry_rank or exit_rank populated
- Mode will be set to 'entry', 'exit', or 'monitor'

---

## 🎉 You're Done!

**Time taken**: ~5-10 minutes  
**Downtime**: None  
**Data lost**: None  
**Backward compatibility**: ✅ Maintained  
**Rollback available**: ✅ Yes  

**Next**: Update Python ranking job to save new ranks!

---

## 📞 Quick Reference

### Check if migration succeeded
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'options_ranks' 
AND column_name IN ('entry_rank', 'exit_rank');
```

### Check existing data
```sql
SELECT ranking_mode, COUNT(*), 
       COUNT(entry_rank) as with_entry, 
       COUNT(exit_rank) as with_exit
FROM options_ranks 
GROUP BY ranking_mode;
```

### Test indexes
```sql
SELECT indexname FROM pg_indexes 
WHERE tablename = 'options_ranks' 
AND indexname LIKE '%entry%';
```

All good? **Let's populate those new ranks with Python!** 🚀
