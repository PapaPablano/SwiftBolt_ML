# Paper Trading Implementation Checklist

**Feature:** Paper Trading with Safe Data Integrity
**Status:** READY FOR DEVELOPMENT
**Blocker Issues:** 4 Critical (must fix before deployment)

---

## Pre-Implementation Review

- [ ] **Stakeholder Approval**
  - [ ] Product Lead approved 2-3 week timeline for fixes
  - [ ] Engineering Lead committed resources
  - [ ] QA Lead prepared test scenarios

- [ ] **Documentation Review**
  - [ ] Read `docs/PAPER_TRADING_RISKS_EXECUTIVE_SUMMARY.md` (5 min)
  - [ ] Read `docs/DATA_INTEGRITY_REVIEW_PAPER_TRADING.md` (30 min)
  - [ ] Understand all 4 critical issues
  - [ ] Understand all 7 secondary issues

- [ ] **Team Alignment**
  - [ ] Database engineer assigned
  - [ ] Backend engineer assigned
  - [ ] Frontend engineer assigned
  - [ ] QA engineer assigned
  - [ ] Team kick-off meeting scheduled

---

## Phase 1: Database Schema Migration (Week 1)

### 1.1 Create Migration File

- [ ] Create file: `supabase/migrations/20260301000000_paper_trading_safe_schema.sql`
- [ ] Copy contents from: `docs/PAPER_TRADING_SAFE_MIGRATION.sql`
- [ ] Verify all ENUMs defined first
- [ ] Verify all constraints in place

### 1.2 Test Migration Locally

- [ ] Start local Supabase: `npx supabase start`
- [ ] Apply migration: `npx supabase db push`
- [ ] Verify tables created: `\dt paper_trading_*`
- [ ] Verify ENUMs created: `\dT`
- [ ] Verify indices: `\di idx_*`

### 1.3 Validate Constraints

Run these SQL commands on local database:

```sql
-- Test NOT NULL constraint
INSERT INTO paper_trading_positions (
  id, user_id, strategy_id, symbol_id, timeframe,
  entry_price, current_price, quantity, entry_time,
  direction, status
) VALUES (
  gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),
  gen_random_uuid(), '1h', NULL, NULL, 10, NOW(), 'long', 'open'
);
-- Expected: ERROR - entry_price is NOT NULL

-- Test direction enum
INSERT INTO paper_trading_positions (..., direction) VALUES (..., 'LONG');
-- Expected: ERROR - invalid enum value 'LONG'

-- Test SL/TP validation (long with SL above entry)
INSERT INTO paper_trading_positions (
  ..., entry_price = 100, stop_loss = 105, direction = 'long', ...
);
-- Expected: ERROR - SL must be below entry for long

-- Test time ordering
INSERT INTO paper_trading_trades (
  ..., entry_time = '2026-02-25 15:00', exit_time = '2026-02-25 14:00', ...
);
-- Expected: ERROR - exit_time must be > entry_time
```

- [ ] All constraints enforced correctly
- [ ] Error messages are clear

### 1.4 Test RLS Policies

```sql
-- Create test user
INSERT INTO auth.users (id, email) VALUES (
  'test-user-1', 'test1@example.com'
);

-- Insert position as service_role
INSERT INTO paper_trading_positions (user_id, ...) VALUES ('test-user-1', ...);

-- Query as different user
SET SESSION "request.jwt.claims" = '{"sub": "test-user-2"}';
SELECT COUNT(*) FROM paper_trading_positions;
-- Expected: 0 rows (hidden by RLS)

-- Query as correct user
SET SESSION "request.jwt.claims" = '{"sub": "test-user-1"}';
SELECT COUNT(*) FROM paper_trading_positions;
-- Expected: 1 row (visible)
```

- [ ] RLS correctly hides other users' data
- [ ] RLS allows users to see only their own data

### 1.5 Test Position Closure Function

```sql
-- Create test data
INSERT INTO paper_trading_positions (
  id, user_id, strategy_id, symbol_id, timeframe,
  entry_price, current_price, quantity, entry_time,
  direction, status
) VALUES (
  'test-pos-1', 'test-user-1', ..., 100, 100, 10,
  NOW() - INTERVAL '1 hour', 'long', 'open'
);

-- Test closure
SELECT close_paper_position('test-pos-1', 105, 'TP_HIT');
-- Expected: Returns trade UUID

-- Verify position is closed
SELECT status FROM paper_trading_positions WHERE id = 'test-pos-1';
-- Expected: 'closed'

-- Verify trade exists
SELECT pnl, pnl_pct FROM paper_trading_trades
WHERE position_id = 'test-pos-1';
-- Expected: pnl = 50, pnl_pct = 5.0

-- Test double-close prevention
SELECT close_paper_position('test-pos-1', 104, 'SL_HIT');
-- Expected: ERROR - Position already closed
```

- [ ] Function correctly calculates PnL
- [ ] Function prevents double-close
- [ ] Function returns trade ID

### 1.6 Code Review

- [ ] Database engineer reviews migration
- [ ] SQL style is correct (lowercase, snake_case)
- [ ] All constraints documented in comments
- [ ] No default-allow RLS policies
- [ ] All foreign keys use appropriate ON DELETE behavior

- [ ] Approve migration for staging

---

## Phase 2: Backend Paper Trading Executor (Week 2)

### 2.1 Create Edge Function Skeleton

- [ ] Create: `supabase/functions/paper-trading-executor/index.ts`

```typescript
// Basic structure
Deno.serve(async (req: Request) => {
  try {
    // 1. Get active strategies
    // 2. Fetch latest bars for each symbol/timeframe
    // 3. Evaluate entry/exit conditions
    // 4. Manage position lifecycle (create, check SL/TP, close)
    // 5. Log executions

    return new Response(JSON.stringify({ success: true }));
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), { status: 500 });
  }
});
```

- [ ] Implement fetching active strategies
- [ ] Implement fetching latest bars
- [ ] Implement condition evaluation
- [ ] Implement position creation (INSERT)
- [ ] Implement position closure (call `close_paper_position()`)
- [ ] Implement execution logging

### 2.2 Test Executor with Real Data

- [ ] Create test strategy with simple conditions
- [ ] Run executor locally with sample market data
- [ ] Verify position created
- [ ] Verify execution log entry created
- [ ] Verify SL/TP logic works
- [ ] Verify exit signal logic works

### 2.3 Race Condition Verification

**Critical Test:** Verify position closure atomicity

```typescript
// Simulate concurrent closes
const pos_id = 'test-pos-1';

const promises = [
  executor.closePosition(pos_id, 105, 'TP_HIT'),
  executor.closePosition(pos_id, 104, 'SL_HIT'),
];

const results = await Promise.allSettled(promises);

// Verify exactly ONE succeeded, ONE failed
assert(results[0].status === 'fulfilled' || results[1].status === 'fulfilled');
assert(results[0].status === 'rejected' || results[1].status === 'rejected');

// Verify exactly ONE trade created
const trades = await db.query(
  'SELECT COUNT(*) FROM paper_trading_trades WHERE position_id = ?',
  pos_id
);
assert(trades[0].count === 1);
```

- [ ] Concurrent closes blocked by database lock
- [ ] Only one trade created per position
- [ ] Second attempt gets clear error

### 2.4 Type Safety

- [ ] All TypeScript types defined
- [ ] All database types match (position_direction enum, etc.)
- [ ] `npx tsc --noEmit` passes
- [ ] Deno linter passes: `deno lint supabase/functions/`
- [ ] Deno formatter passes: `deno fmt --check supabase/functions/`

### 2.5 Code Review

- [ ] Backend engineer reviews executor
- [ ] SQL injection prevention checked (parameterized queries)
- [ ] Error handling comprehensive
- [ ] All database operations atomic
- [ ] Logging sufficient for debugging

- [ ] Approve executor for staging

---

## Phase 3: Frontend Paper Trading Dashboard (Week 2-3)

### 3.1 Create Components

- [ ] `frontend/src/components/PaperTradingDashboard.tsx`
- [ ] `frontend/src/components/OpenPositionsTable.tsx`
- [ ] `frontend/src/components/TradeHistoryTable.tsx`
- [ ] `frontend/src/components/PerformanceMetrics.tsx`
- [ ] `frontend/src/components/BacktestVsPaperComparison.tsx`

### 3.2 Dashboard Queries

- [ ] Query open positions with real-time updates (RLS enforced)
- [ ] Query trade history with pagination
- [ ] Query performance metrics
- [ ] Query execution log for debugging

### 3.3 Real-Time Updates

- [ ] Subscribe to position updates via Supabase Realtime
- [ ] Subscribe to trade completions
- [ ] Update unrealized P&L every candle
- [ ] Update metrics every 5 minutes

### 3.4 UI Features

- [ ] Display open positions (symbol, entry price, current price, unrealized P&L)
- [ ] Display SL and TP levels
- [ ] Display trade history with entry/exit prices
- [ ] Display P&L per trade
- [ ] Show performance metrics (wins, losses, win rate, max DD, Sharpe)
- [ ] Compare backtest vs paper trading P&L
- [ ] Alert if divergence > 10%

### 3.5 Testing

- [ ] Can view dashboard without errors
- [ ] Real-time updates working
- [ ] P&L calculations match backend
- [ ] RLS prevents viewing other users' data

---

## Phase 4: Integration Testing (Week 3)

### 4.1 End-to-End Test Scenarios

**Test 1: Entry Signal → Position Created**
- [ ] Create strategy with simple condition
- [ ] Market data triggers entry condition
- [ ] Executor runs
- [ ] Position created with correct entry price
- [ ] Execution log shows 'entry' signal

**Test 2: SL Hit → Position Closed**
- [ ] Position open at entry_price = 100, SL = 95
- [ ] Market price drops to 94
- [ ] Executor runs
- [ ] Position closed at 95 (SL price)
- [ ] Trade created with pnl = -50
- [ ] Execution log shows 'SL_HIT'

**Test 3: TP Hit → Position Closed**
- [ ] Position open at entry_price = 100, TP = 105
- [ ] Market price rises to 106
- [ ] Executor runs
- [ ] Position closed at 105 (TP price)
- [ ] Trade created with pnl = 50
- [ ] Execution log shows 'TP_HIT'

**Test 4: Exit Signal → Position Closed**
- [ ] Position open with exit condition
- [ ] Condition triggered by market data
- [ ] Executor runs
- [ ] Position closed at market price
- [ ] Trade created with reason 'EXIT_SIGNAL'

**Test 5: Metrics Update**
- [ ] Close 10 trades (5 wins, 5 losses)
- [ ] Metrics computed
- [ ] win_count = 5, loss_count = 5
- [ ] win_rate = 50.0%
- [ ] total_pnl = sum of individual PnLs
- [ ] Sharpe ratio calculated

**Test 6: Backtest vs Paper Comparison**
- [ ] Run backtest on strategy (expected 5% return)
- [ ] Run paper trading on same strategy (actual 3% return)
- [ ] Dashboard shows both
- [ ] Alert displayed (divergence > 2%)

### 4.2 Data Integrity Tests

**Test 7: Race Condition Prevention**
- [ ] Create position
- [ ] Simultaneously close from executor AND manually
- [ ] Verify only ONE trade created
- [ ] Verify second attempt gets error

**Test 8: Immutability Enforcement**
- [ ] Close trade
- [ ] Attempt UPDATE on trade (should fail)
- [ ] Attempt DELETE on trade (should fail)
- [ ] Verify RLS blocks operation

**Test 9: Constraint Validation**
- [ ] Attempt to create position with entry_price = NULL (should fail)
- [ ] Attempt to create trade with exit_time before entry_time (should fail)
- [ ] Attempt to create position with negative quantity (should fail)

**Test 10: RLS Enforcement**
- [ ] User A creates positions
- [ ] User B queries positions
- [ ] Verify User B cannot see User A's positions
- [ ] Verify User A cannot see User B's positions

### 4.3 Performance Tests

- [ ] 100 concurrent strategies running paper trading executor
- [ ] Executor completes in < 500ms per symbol
- [ ] Dashboard loads with 1000+ historical trades in < 2 seconds
- [ ] Real-time updates latency < 1 second

### 4.4 Run Test Suite

```bash
# Backend tests
cd ml && pytest ml/tests/paper_trading/ -v

# Integration tests
pytest ml/tests/integration/paper_trading_e2e.py -v

# Frontend tests
cd frontend && npm test -- PaperTradingDashboard.test.tsx
```

- [ ] All tests passing
- [ ] Test coverage > 80%
- [ ] No SQL injection vulnerabilities
- [ ] No RLS bypasses

---

## Phase 5: Staging & Validation (Week 4)

### 5.1 Deploy to Staging

- [ ] Merge to staging branch
- [ ] Run full migration suite on staging database
- [ ] Verify no data loss
- [ ] Verify all indices created
- [ ] Verify all RLS policies active

### 5.2 User Acceptance Testing

Invite 2-3 users to test paper trading on staging:

- [ ] Can enable paper trading on a strategy
- [ ] Can manually run paper trading executor
- [ ] Can see open positions in real-time
- [ ] Can see trade history with P&L
- [ ] Dashboard updates without page refresh
- [ ] Backtest vs paper comparison makes sense
- [ ] No confusing error messages

- [ ] Gather feedback
- [ ] Fix UI issues
- [ ] Document any data quirks

### 5.3 Production Readiness Checklist

- [ ] Database migration tested on staging
- [ ] Executor Edge Function deployed and working
- [ ] Dashboard fully functional
- [ ] All tests passing
- [ ] No data integrity issues
- [ ] Documentation updated
- [ ] Monitoring/alerting configured

### 5.4 Rollback Plan

- [ ] Document how to revert migration if issues arise
- [ ] Have backup of current database schema
- [ ] Document how to disable paper trading for users
- [ ] Test rollback procedure on staging

---

## Phase 6: Production Deployment (Week 4)

### 6.1 Pre-Deployment

- [ ] Schedule deployment (off-peak hours)
- [ ] Notify users of new feature
- [ ] Have monitoring dashboard ready
- [ ] Have Slack escalation channel ready

### 6.2 Deploy Database

```bash
# Create backup
pg_dump <prod_db> > backup_prod_$(date +%s).sql

# Apply migration
npx supabase migrations deploy --db-url <prod_url>

# Verify
psql <prod_url> -c "\dt paper_trading_*"
```

- [ ] Migration applied successfully
- [ ] No errors in logs
- [ ] All tables created
- [ ] All indices created

### 6.3 Deploy Backend

```bash
# Deploy executor function
npx supabase functions deploy paper-trading-executor
```

- [ ] Function deployed
- [ ] Can invoke successfully
- [ ] No errors in logs

### 6.4 Deploy Frontend

```bash
# Build and deploy dashboard
cd frontend && npm run build
# Deploy to hosting
```

- [ ] Dashboard loads
- [ ] Can access paper trading feature
- [ ] Real-time updates working

### 6.5 Post-Deployment Monitoring

- [ ] Monitor database performance (slow queries)
- [ ] Monitor executor function latency
- [ ] Monitor user error reports
- [ ] Check Sentry for exceptions
- [ ] Verify correct P&L calculations (sample 10 trades)

**Monitor for 24 hours after deployment:**

```sql
-- Check for any stuck positions
SELECT COUNT(*) FROM paper_trading_positions
WHERE status = 'open'
AND entry_time < NOW() - INTERVAL '4 hours';

-- Check for orphaned trades
SELECT COUNT(*) FROM paper_trading_trades
WHERE position_id NOT IN (SELECT id FROM paper_trading_positions);

-- Check for constraint violations
SELECT COUNT(*) FROM paper_trading_trades
WHERE exit_time <= entry_time;
```

- [ ] No issues detected
- [ ] All metrics healthy
- [ ] Users happy with feature

---

## Success Criteria

- [ ] Paper trading enabled for strategies
- [ ] Positions tracked accurately
- [ ] Trades closed at correct prices
- [ ] P&L calculations verified
- [ ] Dashboard responsive
- [ ] No data corruption
- [ ] No race conditions
- [ ] No security issues
- [ ] Users can compare backtest vs paper
- [ ] Audit trail immutable and complete

---

## Sign-Off

- [ ] Database Engineer: _____________________ Date: _______
- [ ] Backend Engineer: _____________________ Date: _______
- [ ] Frontend Engineer: _____________________ Date: _______
- [ ] QA Lead: _____________________ Date: _______
- [ ] Product Lead: _____________________ Date: _______
- [ ] Data Integrity Guardian: _____________________ Date: _______

**All signatures required before production deployment.**

---

## Useful References

- Migration script: `docs/PAPER_TRADING_SAFE_MIGRATION.sql`
- Risk analysis: `docs/DATA_INTEGRITY_REVIEW_PAPER_TRADING.md`
- Executive summary: `docs/PAPER_TRADING_RISKS_EXECUTIVE_SUMMARY.md`
- Feature plan: `docs/plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md`
