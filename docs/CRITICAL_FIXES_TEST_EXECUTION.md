# Critical Fixes - Complete Test Execution Guide

**Status:** All test files created and ready to execute
**Purpose:** Verify that all critical and high priority fixes are working correctly

---

## Test Files Created

### 1. Security & Integrity Tests
**File:** `supabase/functions/paper-trading-executor/executor_security_test.ts`
**Tests:** 18 test cases covering 7 critical/high fixes

```
CRITICAL #1: RLS Policies (3 tests)
  - Cross-user access prevention
  - Cross-user modification prevention
  - Immutable audit trail

CRITICAL #2: Slippage Validation (3 tests)
  - Rejects >5.0%
  - Accepts valid range [0.01%, 5.0%]
  - Default 2.0%

CRITICAL #3: Position Constraints (4 tests)
  - Entry price > 0
  - Quantity in [1, 1000]
  - Long position: SL < Entry < TP
  - Short position: TP < Entry < SL

HIGH #4: Race Condition (3 tests)
  - FOR UPDATE lock prevents concurrent closes
  - Returns RACE_CONDITION error
  - No phantom duplicate trades

HIGH #5: Market Data Validation (4 tests)
  - Rejects null OHLC
  - Validates high >= low
  - Validates close within [low, high]
  - Detects gaps >10%

HIGH #6: Condition Evaluator Unification (3 tests)
  - Single source of truth
  - Indicator caching
  - Type-safe discriminated unions

HIGH #7: Database Indices (3 tests)
  - Composite index coverage
  - DESC timestamp ordering
  - <50ms latency target
```

**Run with:**
```bash
cd supabase/functions/paper-trading-executor
deno test --allow-env executor_security_test.ts
```

**Expected Output:**
```
running 18 tests from executor_security_test.ts
✓ CRITICAL #1: RLS - User cannot access other user's positions
✓ CRITICAL #1: RLS - Users cannot modify other user's positions
✓ CRITICAL #1: RLS - Immutable audit trail prevents trade modification
✓ CRITICAL #2: Slippage - Constraint rejects >5.0%
✓ CRITICAL #2: Slippage - Constraint accepts valid range [0.01%, 5.0%]
✓ CRITICAL #2: Slippage - Default 2.0% is reasonable
✓ CRITICAL #3: Position Constraints - Entry price must be > 0
✓ CRITICAL #3: Position Constraints - Quantity in [1, 1000]
✓ CRITICAL #3: Position Constraints - SL < Entry < TP for long
✓ CRITICAL #3: Position Constraints - TP < Entry < SL for short
✓ HIGH #4: Race Condition - FOR UPDATE lock prevents concurrent closes
✓ HIGH #4: Race Condition - Returns RACE_CONDITION error
✓ HIGH #4: Race Condition - No phantom duplicate trades
✓ HIGH #5: Market Data - Rejects null OHLC
✓ HIGH #5: Market Data - Validates high >= low
✓ HIGH #5: Market Data - Validates close within [low, high]
✓ HIGH #5: Market Data - Detects gaps >10%
✓ Summary: All critical and high fixes implemented

test result: ok. 18 passed (xxx ms)
```

---

### 2. End-to-End Integration Tests
**File:** `supabase/functions/paper-trading-executor/executor_e2e_test.ts`
**Tests:** 9 real-world scenarios

```
Scenario 1: RSI > 70 entry signal
Scenario 2: RSI < 30 exit signal
Scenario 3: Multi-condition entry (RSI > 70 AND Volume > avg)
Scenario 4: Crossover signal (Price > MA20)
Scenario 5: Stop loss hit
Scenario 6: Take profit hit
Scenario 7: Paper trading ↔ backtest parity
Scenario 8: 5+ concurrent strategies <500ms
Scenario 9: Indicator caching reuse
```

**Run with:**
```bash
cd supabase/functions/paper-trading-executor
deno test --allow-env executor_e2e_test.ts
```

**Expected Output:**
```
running 9 tests from executor_e2e_test.ts
✓ E2E: Simple RSI > 70 entry signal triggers position creation
✓ E2E: RSI < 30 exit signal closes position
✓ E2E: Multi-condition entry (RSI > 70 AND Volume > avg) triggers position
✓ E2E: Crossover signal (Price > MA20) triggers entry
✓ E2E: Stop loss hit closes position automatically
✓ E2E: Take profit hit closes position automatically
✓ E2E: Paper trading results match backtest results (parity test)
✓ E2E: Executor handles 5+ concurrent strategies <500ms per strategy
✓ E2E: Indicator caching calculates RSI once, reuses for multiple conditions
✓ E2E: All scenarios verified - backtest ↔ paper parity confirmed

=== END-TO-END SCENARIOS COMPLETE ===
✓ HIGH PRIORITY FIX #6 VERIFIED: Condition evaluator unified

test result: ok. 9 passed (xxx ms)
```

---

### 3. Performance Benchmark Guide
**File:** `docs/PERFORMANCE_BENCHMARK_PLAN.md`
**Manual Tests:** 7 database queries with latency targets

**Queries to benchmark:**
1. Open positions query - target: <50ms
2. Trade history query - target: <100ms
3. Dashboard metrics - target: <200ms
4. Position status check - target: <10ms
5. Executor latency - target: <500ms per strategy
6. Chart render 1000 trades - target: <200ms

**How to run:**
```bash
# Connect to Supabase database
psql -h $SUPABASE_HOST -U $SUPABASE_USER -d $SUPABASE_DB

# Run each EXPLAIN ANALYZE query from the benchmark plan
# Record "Execution Time" values
# Verify all meet targets
```

---

## Complete Test Execution Workflow

### Phase 1: Unit Tests (Security & Integrity) - 5 minutes

```bash
# Step 1: Run security test suite
cd supabase/functions/paper-trading-executor
deno test --allow-env executor_security_test.ts

# Expected: 18/18 passing
# Time: ~5 seconds
# Verifies: All 7 critical/high issues implemented correctly
```

### Phase 2: Integration Tests (E2E Scenarios) - 10 minutes

```bash
# Step 2: Run end-to-end test suite
cd supabase/functions/paper-trading-executor
deno test --allow-env executor_e2e_test.ts

# Expected: 9/9 passing
# Time: ~10 seconds
# Verifies: Full workflow from strategy to trade execution
```

### Phase 3: Performance Tests (Database Queries) - 30 minutes

```bash
# Step 3: Connect to Supabase database
psql -h $SUPABASE_HOST -U $SUPABASE_USER -d $SUPABASE_DB

# Step 4: Run each EXPLAIN ANALYZE query
# See PERFORMANCE_BENCHMARK_PLAN.md for queries

# Record latencies:
# Query 1 (open positions): ___ ms (target: <50ms)
# Query 2 (trade history): ___ ms (target: <100ms)
# Query 3 (dashboard): ___ ms (target: <200ms)
# Query 4 (position status): ___ ms (target: <10ms)

# Step 5: Verify all latencies meet targets
# If any query exceeds target:
#   - Check index usage in EXPLAIN output
#   - Run ANALYZE on table if needed
#   - Check for missing indices
```

---

## Success Criteria

### ✅ All Tests Pass
- Unit tests: 18/18
- Integration tests: 9/9
- Performance: 7/7 queries < target

### ✅ All Critical Issues Verified
- RLS policies prevent cross-user access
- Slippage bounded [0.01%, 5.0%]
- Position constraints enforced
- Race conditions prevented with locks
- Market data validation working
- Condition evaluator unified
- Database indices optimizing queries

### ✅ Real-World Scenarios Tested
- Simple signals (RSI, MA crossover)
- Multi-condition AND/OR logic
- SL/TP exit scenarios
- Concurrent execution
- Indicator caching
- Backtest ↔ paper parity

### ✅ Performance Targets Met
- <50ms for position queries
- <100ms for trade history
- <200ms for dashboard
- <500ms executor latency
- <200ms chart render (1000 trades)

---

## Troubleshooting

### If Security Tests Fail

**Problem:** "User can access other user's positions"
**Solution:** Check that RLS is enabled and policies are applied
```sql
SELECT tablename, enable_rls FROM pg_tables
WHERE tablename LIKE 'paper_trading%';
```

**Problem:** "Slippage validation not working"
**Solution:** Verify CHECK constraint exists
```sql
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_name = 'strategy_user_strategies'
AND constraint_type = 'CHECK';
```

### If Integration Tests Fail

**Problem:** "Entry signal not creating position"
**Solution:** Check condition evaluator logic matches backtest
**Fix:** Ensure both use same evaluateCondition() function

**Problem:** "Exit price doesn't match manual calculation"
**Solution:** Check P&L calculation formula
**Fix:** (exit_price - entry_price) * quantity, with proper sign for short

### If Performance Tests Fail

**Problem:** "Query takes >50ms"
**Solution:** Index not being used
**Fix:** Check EXPLAIN ANALYZE - should show "Index Scan" not "Seq Scan"

**Problem:** "Still seeing sequential scan"
**Solution:** Statistics outdated
**Fix:** Run `ANALYZE paper_trading_positions;`

---

## Next Steps After Tests Pass

1. **Code Review** - Review test files and implementations
2. **Documentation** - Update README with test results
3. **Deployment** - Schedule production deployment
4. **Monitoring** - Set up alerts for latency/errors
5. **Validation** - Monitor first 24 hours in production

---

## Test Artifacts to Collect

After running tests, collect:

```
├── test-results/
│   ├── security-tests.log
│   ├── e2e-tests.log
│   ├── performance-benchmarks.csv
│   └── test-summary.md
```

**Create summary report:**
```markdown
# Test Execution Summary

**Date:** 2026-02-26
**Duration:** 45 minutes

## Results
- Security tests: 18/18 ✅
- E2E tests: 9/9 ✅
- Performance tests: 7/7 ✅

## Latencies
- Position query: 28ms (target: <50ms) ✅
- Trade history: 67ms (target: <100ms) ✅
- Dashboard: 145ms (target: <200ms) ✅
- Executor: 150ms for 5 strategies (target: <500ms) ✅

## Conclusion
All critical and high priority fixes verified working.
System ready for production deployment.
```

---

## Estimated Timeline

- **Unit tests:** 5 min
- **Integration tests:** 10 min
- **Performance tests:** 30 min
- **Review & documentation:** 15 min
- **Total:** ~60 minutes for full verification

---

## Running All Tests at Once

```bash
#!/bin/bash

echo "=== PHASE 1: Security & Integrity Tests ==="
cd supabase/functions/paper-trading-executor
deno test --allow-env executor_security_test.ts

echo "=== PHASE 2: End-to-End Scenarios ==="
deno test --allow-env executor_e2e_test.ts

echo "=== PHASE 3: Performance Benchmarks ==="
echo "Run manual queries from docs/PERFORMANCE_BENCHMARK_PLAN.md"
echo "Update docs/TEST_RESULTS.md with latencies"

echo "=== ALL TESTS COMPLETE ==="
```

Save as: `scripts/run-all-critical-tests.sh`

---

**Status:** ✅ Ready to execute all tests
**Next:** Run test suite and collect results
