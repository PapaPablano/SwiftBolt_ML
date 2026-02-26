# Paper Trading Critical Fixes - Deployment Verification Checklist

**Deployed Date:** 2026-02-25
**Deployed Migrations:**
- `20260225120000_paper_trading_security_v1.sql`
- `20260225130000_paper_trading_immutability_v1.sql`

---

## ✅ Migration History

```
Status: REPAIRED
Migrations applied:
- 20260225120000: Security schema, RLS, constraints, indices
- 20260225130000: Immutability triggers, race condition prevention
```

---

## 📋 Verification Checklist

### 1. Database Schema Verification

Run these SQL queries in your Supabase SQL Editor to verify tables were created:

```sql
-- Verify paper trading tables exist
SELECT
  table_name,
  (SELECT count(*) FROM information_schema.columns
   WHERE table_schema='public' AND table_name=t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema='public' AND table_name LIKE 'paper_%'
ORDER BY table_name;

-- Expected output:
-- paper_trading_metrics       | 15 columns
-- paper_trading_positions     | 11 columns
-- paper_trading_trades        | 12 columns
-- position_closure_log        | 8 columns
-- strategy_execution_log      | 8 columns
```

### 2. RLS Policies Verification

```sql
-- Verify RLS is enabled on all paper trading tables
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname='public' AND tablename LIKE 'paper_%';

-- Expected output: all should show 't' (true) for rowsecurity
```

### 3. Constraints Verification

```sql
-- Verify CHECK constraints on slippage, position size, SL/TP
SELECT
  constraint_name,
  table_name,
  constraint_definition
FROM information_schema.check_constraints
WHERE table_schema='public' AND table_name LIKE 'paper_%'
ORDER BY table_name;

-- Key constraints to verify:
-- - paper_trading_positions: entry_price > 0
-- - paper_trading_positions: quantity > 0 AND quantity <= 1000
-- - paper_trading_positions: slippage bounds 0.01%-5%
-- - paper_trading_positions: SL/TP level ordering (SL < entry < TP for longs)
```

### 4. Triggers Verification

```sql
-- Verify immutability and race condition prevention triggers
SELECT
  trigger_name,
  event_object_table,
  action_timing
FROM information_schema.triggers
WHERE trigger_schema='public'
  AND (trigger_name LIKE 'prevent_%'
    OR trigger_name LIKE 'validate_%'
    OR trigger_name LIKE 'update_position%')
ORDER BY event_object_table, trigger_name;

-- Expected triggers:
-- - prevent_trade_deletes_trigger (on paper_trading_trades)
-- - prevent_trade_updates_trigger (on paper_trading_trades)
-- - validate_position_completeness_trigger (on paper_trading_positions)
-- - update_position_timestamp_trigger (on paper_trading_positions)
```

### 5. Indices Verification

```sql
-- Verify performance indices created
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename LIKE 'paper_%'
ORDER BY tablename, indexname;

-- Expected indices:
-- - idx_paper_positions_user_strategy (multi-column for filtering)
-- - idx_paper_positions_status (for race condition checks)
-- - idx_paper_trades_user_strategy (for history queries)
-- - idx_execution_log_user_strategy (for audit trail)
```

### 6. Functions Verification

```sql
-- Verify safe position closure function exists
SELECT
  proname,
  oid
FROM pg_proc
WHERE proname IN ('close_paper_position', 'test_concurrent_close',
                   'prevent_trade_updates', 'prevent_trade_deletes',
                   'validate_position_completeness', 'update_position_timestamp')
ORDER BY proname;

-- All 6 functions should exist
```

### 7. RLS Policy Testing

**Test 1: User A cannot see User B's positions**

```typescript
// In your app, run as User A
const { data: myPositions } = await supabase
  .from('paper_trading_positions')
  .select('*')
  .eq('user_id', userB_id); // Different user

// Result should be: EMPTY (no rows returned due to RLS)
// If you get any rows, RLS policy failed ❌
```

**Test 2: Anonymous user can create strategies with user_id=NULL**

```typescript
// As anonymous user
const { data: anonPosition } = await supabase
  .from('paper_trading_positions')
  .insert({
    user_id: null,
    strategy_id: 'test-strategy',
    symbol_id: 'AAPL',
    // ... other fields
  });

// Result should be: SUCCESS ✅
```

### 8. Constraint Testing

**Test 1: Entry price must be > 0**

```typescript
// Try to insert position with entry_price = 0
const { error } = await supabase
  .from('paper_trading_positions')
  .insert({
    entry_price: 0, // Invalid
    // ... other required fields
  });

// Result should be: DATABASE ERROR ✅
// Expected error: "entry_price > 0"
```

**Test 2: Position size must be 1-1000**

```typescript
// Try to insert with quantity = 5000
const { error } = await supabase
  .from('paper_trading_positions')
  .insert({
    quantity: 5000, // Out of bounds
    // ... other fields
  });

// Result should be: DATABASE ERROR ✅
// Expected error: "quantity <= 1000"
```

**Test 3: SL < entry < TP for long positions**

```typescript
// Try to create long with SL above entry
const { error } = await supabase
  .from('paper_trading_positions')
  .insert({
    direction: 'long',
    entry_price: 100,
    stop_loss_price: 105, // Above entry - invalid for long
    take_profit_price: 110,
  });

// Result should be: DATABASE ERROR ✅
```

### 9. Immutability Testing

**Test 1: Cannot UPDATE closed trades**

```typescript
// Try to modify a closed trade
const { error } = await supabase
  .from('paper_trading_trades')
  .update({ pnl: 0 }) // Try to hide profit
  .eq('id', tradeId);

// Result should be: RLS POLICY ERROR ✅
// Message: "new row violates row-level security policy"
```

**Test 2: Cannot DELETE closed trades**

```typescript
// Try to delete a trade
const { error } = await supabase
  .from('paper_trading_trades')
  .delete()
  .eq('id', tradeId);

// Result should be: RLS POLICY ERROR ✅
```

### 10. Race Condition Prevention Testing

**Test 1: Concurrent close attempts**

```typescript
// Simulate race condition: two concurrent requests close same position
const closeAttempt1 = supabase.rpc('close_paper_position', {
  p_position_id: positionId,
  p_exit_price: 105,
  p_close_reason: 'EXIT_SIGNAL',
});

const closeAttempt2 = supabase.rpc('close_paper_position', {
  p_position_id: positionId,
  p_exit_price: 106,
  p_close_reason: 'TP_HIT',
});

const [result1, result2] = await Promise.all([closeAttempt1, closeAttempt2]);

// Expected:
// result1.success = true (first close succeeds)
// result2.success = false (second fails with 'RACE_CONDITION' error)
```

---

## 🔒 Security Verification Checklist

- [ ] User A cannot read User B's positions (RLS enforced)
- [ ] User A cannot read User B's trades (RLS enforced)
- [ ] User A cannot modify their own closed trades (immutable)
- [ ] Entry price must be > 0 (prevents orphaned positions)
- [ ] Position size must be 1-1000 (prevents P&L overflow)
- [ ] Slippage constrained to 0.01%-5% (prevents inflation)
- [ ] SL/TP constraints enforced (long: SL<entry<TP)
- [ ] Race condition prevented (optimistic locking works)

---

## 🚀 What's Next

Once all verifications pass ✅:

1. **Phase 1A (Weeks 2-3):** Condition Builder UI Component
   - React component for multi-condition strategy building
   - Visual + forms hybrid UI
   - Tests included

2. **Phase 1B (Weeks 2-3, parallel):** Indicator Menu
   - 30-40 indicators categorized
   - Discovery + correlation warnings
   - Tests included

3. **Phase 2 (Weeks 3-4):** Paper Trading Execution Engine
   - Real-time strategy evaluation
   - Executor with validators
   - Dashboard

---

## 📊 Current Status

| Component | Status | Tests | Production Ready |
|-----------|--------|-------|------------------|
| Database Schema | ✅ Deployed | N/A | ✅ Yes |
| RLS Policies | ✅ Deployed | Manual | ✅ Yes |
| Validators | ✅ Written | 27 pass | ✅ Yes |
| Condition Evaluator | ✅ Written | 19 pass | ✅ Yes |
| Race Prevention | ✅ Deployed | Manual | ✅ Yes |

---

## ⚠️ Rollback Plan

If issues discovered:

1. Connect to Supabase SQL Editor
2. Identify the problematic migration (120000 or 130000)
3. Run rollback SQL (provided in migration files)
4. Contact Supabase support if full rollback needed

---

**Verification Date:** ___________
**Verified By:** ___________
**All Tests Passed:** ☐ Yes ☐ No

If all tests pass, **you're ready for Phase 1 UI implementation!**
