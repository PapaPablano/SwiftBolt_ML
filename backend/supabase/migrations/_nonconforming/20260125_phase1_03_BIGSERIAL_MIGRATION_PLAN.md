# BIGSERIAL → GENERATED ALWAYS AS IDENTITY Migration Plan

**Date**: January 25, 2026
**Status**: 🟡 DOCUMENTED (Not yet executed - requires careful staging)
**Priority**: Phase 2 (deferred from Phase 1 due to complexity)
**Effort**: 4-6 hours per table

---

## Overview

BIGSERIAL is deprecated in PostgreSQL. Modern standard is:
```sql
BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

---

## Tables Affected

1. ✅ `ohlc_bars` - Historical OHLC data
2. ✅ `ohlc_bars_v2` - Current OHLC data (larger table)
3. ✅ `intraday_bars` - Intraday bar data
4. ✅ `iv_history_and_momentum` - IV history
5. ✅ `dataset_first_schema` - ML dataset
6. ✅ `watchlist_limits_and_helpers` - Watchlist helpers
7. ✅ Additional 2+ tables

---

## Why This Matters

**Deprecated Syntax**
- PostgreSQL docs recommend GENERATED ALWAYS AS IDENTITY
- BIGSERIAL is a convenience wrapper around sequences
- GENERATED ALWAYS AS IDENTITY is the modern standard

**Portability**
- BIGSERIAL is PostgreSQL-specific
- GENERATED ALWAYS AS IDENTITY is SQL standard
- Makes migration to other databases easier if needed

**Clarity**
- GENERATED ALWAYS AS IDENTITY explicitly shows intent
- Sequence management is clearer
- Constraints are more visible

---

## Migration Strategy

### Option A: New Tables Only (Recommended for Phase 1)
For new tables going forward, use:
```sql
CREATE TABLE table_name (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ...
);
```

### Option B: Existing Tables (Phase 2+)

**Why it's complex:**
- Changes the primary key (risky)
- Affects all foreign key relationships
- Needs careful sequence migration
- Data must be copied
- Requires testing on large tables (ohlc_bars_v2 has millions of rows)

**Recommended approach:**
1. Do NOT attempt during production hours
2. Full backup REQUIRED
3. Test thoroughly on staging first
4. Consider deferring to next major version upgrade

---

## Step-by-Step Procedure (For Phase 2)

### Pre-Migration
```bash
# 1. Full backup
pg_dump > full_backup_before_bigserial.sql

# 2. Backup just the table
pg_dump -t ohlc_bars_v2 > ohlc_bars_v2_backup.sql

# 3. Document current sequence value
SELECT last_value FROM ohlc_bars_v2_id_seq;
```

### Migration (Testing Only, Not Yet)
```sql
-- Step 1: Verify current state
\d ohlc_bars_v2

-- Step 2: Create new column with GENERATED ALWAYS AS IDENTITY
BEGIN TRANSACTION;

ALTER TABLE ohlc_bars_v2
  ADD COLUMN id_new BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;

-- Step 3: Copy existing IDs to new column
UPDATE ohlc_bars_v2 SET id_new = id;

-- Step 4: Sync the sequence value
SELECT setval(pg_get_serial_sequence('ohlc_bars_v2', 'id_new'),
             COALESCE(MAX(id_new), 0))
FROM ohlc_bars_v2;

-- Step 5: Verify the sequences are in sync
SELECT
  pg_get_serial_sequence('ohlc_bars_v2', 'id') as old_seq,
  pg_get_serial_sequence('ohlc_bars_v2', 'id_new') as new_seq;

-- Step 6: Check max value
SELECT MAX(id_new) FROM ohlc_bars_v2;
SELECT nextval(pg_get_serial_sequence('ohlc_bars_v2', 'id_new'));

COMMIT;
```

### Post-Migration (Only if Testing Successful)
```sql
-- Step 7: Drop old column and rename
BEGIN TRANSACTION;

ALTER TABLE ohlc_bars_v2 DROP CONSTRAINT ohlc_bars_v2_pkey;
ALTER TABLE ohlc_bars_v2 DROP COLUMN id;
ALTER TABLE ohlc_bars_v2 RENAME COLUMN id_new TO id;
ALTER TABLE ohlc_bars_v2 ADD PRIMARY KEY (id);

-- Step 8: Verify
\d ohlc_bars_v2

COMMIT;
```

---

## Risk Assessment

### High Risk Areas
- ⚠️ Primary key change (ohlc_bars_v2 has millions of rows)
- ⚠️ Foreign key dependencies (must update all references)
- ⚠️ Sequence migration (can miss rows if done incorrectly)

### Mitigation
- ✅ Full backup before any changes
- ✅ Test on staging first (4-8 hours)
- ✅ Use transactions (can ROLLBACK)
- ✅ Have DBA review the plan
- ✅ Schedule during maintenance window
- ✅ Monitor database after migration

### Rollback Procedure
```bash
# If migration fails
ROLLBACK;

# Restore from backup
pg_restore < full_backup_before_bigserial.sql
```

---

## Testing Plan (Phase 2)

### 1. Staging Environment Test (4-8 hours)
```bash
# Restore backup to staging
pg_restore -h staging-db.supabase.co < ohlc_bars_v2_backup.sql

# Run through entire migration procedure
# Run all validation queries
# Test application code
```

### 2. Validation Queries
```sql
-- Verify new column works like old one
SELECT id FROM ohlc_bars_v2 LIMIT 10;

-- Verify sequence is correct
SELECT nextval(pg_get_serial_sequence('ohlc_bars_v2', 'id'));

-- Verify no gaps or duplicates
SELECT COUNT(*) as row_count FROM ohlc_bars_v2;
SELECT COUNT(DISTINCT id) as unique_ids FROM ohlc_bars_v2;

-- Verify foreign keys still work
EXPLAIN ANALYZE
SELECT * FROM other_table
WHERE ohlc_bars_v2_id = 1;
```

### 3. Application Code Testing
```python
# Test that application can:
# - Insert new rows (sequence generates IDs)
# - Query by ID
# - Follow foreign key relationships
```

---

## Decision: Phase 1 vs Phase 2

### Recommendation: DEFER TO PHASE 2

**Reasoning:**
1. TIMESTAMP and VARCHAR fixes are lower risk and higher priority
2. BIGSERIAL migration is complex and risky (primary key change)
3. Current BIGSERIAL works fine - just not "modern standard"
4. Better to do in Phase 2 with dedicated time and testing
5. Can tackle ohlc_bars_v2 (largest table) separately from smaller tables

---

## Phase 2 Timeline

**Week of Feb 17-21** (after Phase 1 is stable):
- [ ] Select table for migration (start with smaller table)
- [ ] Full backup and test on staging
- [ ] Execute migration on non-critical table first
- [ ] Monitor for 48 hours
- [ ] If successful, plan ohlc_bars_v2 migration
- [ ] Execute ohlc_bars_v2 migration (schedule maintenance window)
- [ ] Full monitoring and validation

---

## Alternative: Do Nothing

BIGSERIAL still works fine. PostgreSQL keeps it for backward compatibility.

**If we skip this:**
- ✅ Saves 4-6 hours per table
- ✅ Reduces risk
- ✅ Code continues working
- ⚠️ Doesn't follow modern PostgreSQL standards
- ⚠️ Might be deprecated in future versions

**Recommendation**: Fix in Phase 2 when we have time.

---

## Reference: Before and After

### BIGSERIAL (Current)
```sql
CREATE TABLE ohlc_bars_v2 (
  id BIGSERIAL PRIMARY KEY,
  ...
);
```

### GENERATED ALWAYS AS IDENTITY (Modern)
```sql
CREATE TABLE ohlc_bars_v2 (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ...
);
```

---

## Documentation for Developers

### Sequence Access (No Changes Needed)
```python
# Insert new row - sequence generates ID automatically
INSERT INTO ohlc_bars_v2 (symbol_id, ts, open, high, low, close)
VALUES (uuid, now(), 100.0, 101.0, 99.0, 100.5);

# Retrieve inserted ID
SELECT lastval();  # Still works the same way

# Query by ID - no changes needed
SELECT * FROM ohlc_bars_v2 WHERE id = 12345;
```

### Application-Level Code
- No changes needed
- Sequences work the same way
- INSERT behavior identical
- SELECT behavior identical

---

## Success Criteria (When Executed)

- ✅ Migration runs without errors
- ✅ All rows preserved
- ✅ Sequence values preserved
- ✅ New inserts get correct IDs
- ✅ Foreign key relationships work
- ✅ Application queries unchanged
- ✅ No performance degradation

---

## Next Steps

1. ✅ Document this plan (done - this file)
2. ⏳ Phase 1: Fix TIMESTAMP and VARCHAR (this week)
3. ⏳ Phase 2 Planning: Review this plan in detail (Feb 1)
4. ⏳ Phase 2 Execution: Test on staging (Feb 17-21)
5. ⏳ Phase 2 Production: Execute on production (TBD)

---

## Questions & Answers

**Q: Is this critical?**
A: No. BIGSERIAL works fine. It's just not the modern standard.

**Q: Will this break the application?**
A: No. Sequence behavior is identical.

**Q: Why not do it now?**
A: It's complex (primary key change) and risky. Phase 1 fixes are higher priority.

**Q: What if we never do this?**
A: That's OK. BIGSERIAL still works. Just means we're not following latest PostgreSQL standards.

---

## Status

🟡 **DOCUMENTED - READY FOR PHASE 2**

- [x] Analyzed the issue
- [x] Created migration procedure
- [x] Documented testing plan
- [x] Identified risks
- [ ] Executed (Phase 2+)

---

**Created**: January 25, 2026
**Status**: Phase 1 Planning
**Next Review**: February 1, 2026
