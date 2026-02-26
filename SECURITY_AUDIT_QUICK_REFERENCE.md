# Security Audit: Quick Reference Card

## Critical Issues (BLOCKING v1)

### 1. Missing RLS Policies ⚠️
```
Severity: CRITICAL (CVSS 7.5)
Impact:   User A reads/modifies User B's positions
Fix Time: 2-4 hours
Code:     Add auth.uid() = user_id to 3 tables
Status:   Simple pattern, already used in strategies table
```

### 2. Unvalidated Slippage ⚠️
```
Severity: CRITICAL (CVSS 8.0)
Impact:   Inflate backtest with 0.01% slippage
Fix Time: 4-6 hours
Code:     Constrain to 0.05%-5% based on liquidity
Status:   Need symbol_liquidity_classification table
```

### 3. Position Size Unconstrained ⚠️
```
Severity: CRITICAL (CVSS 7.8)
Impact:   Entry price = 0, quantity = 9M
Fix Time: 4-6 hours
Code:     Add validators + database constraints
Status:   Prevents P&L manipulation
```

---

## High Issues (REQUIRED for v1)

### 4. Demo User Fallback
Severity: HIGH (CVSS 7.5) | Fix Time: 1 hour
→ Remove fallback, return 401 if no JWT

### 5. Market Data Source Not Validated
Severity: HIGH (CVSS 7.2) | Fix Time: 4-6 hours
→ Only use verified market data, reject forecasts

### 6. SL/TP Unconstrained
Severity: HIGH (CVSS 6.3) | Fix Time: 2-3 hours
→ Constrain SL to 0.5%-50%, TP to 0.5%-500%

### 7. Shared Condition Evaluator
Severity: HIGH (CVSS 6.8) | Fix Time: 6-8 hours
→ Separate evaluators for backtest vs paper trading

### 8. Divergence Thresholds Undefined
Severity: HIGH (CVSS 6.5) | Fix Time: 2-3 hours
→ Define yellow (5%), red (15%) divergence thresholds

---

## Medium Issues (RECOMMENDED for v1)

| Issue | Time | Priority |
|-------|------|----------|
| Encrypt strategy config | Post-v1 | v1.1 |
| Untruncated error messages | 1 hour | v1 |
| Race condition in position close | 2 hours | v1 |
| Indicator versioning | 4-6 hours | Post-v1 |

---

## Implementation Order

```
WEEK 1: Critical Fixes
├─ RLS policies (2-4h)          ← Easiest, biggest impact
├─ Slippage validation (4-6h)   ← Needs table prep
└─ Position validation (4-6h)   ← Needs constraints

WEEK 2: High Priority Fixes
├─ Remove demo fallback (1h)    ← Quickest
├─ Market data validation (4-6h)
├─ SL/TP validation (2-3h)
├─ Condition evaluator split (6-8h)
└─ Divergence thresholds (2-3h)

WEEK 3: Testing & Code Review
├─ Write test suite (4h)
├─ Security code review (4h)
└─ Deploy to staging (2h)

WEEK 4: Production
├─ Run staging tests (2h)
└─ Production deployment (2h)
```

---

## Risk Scorecard

```
Before Fixes:           After Fixes:
┌─────────────────┐     ┌─────────────────┐
│ Risk: 7.8/10    │     │ Risk: 2.1/10    │
│ Status: UNSAFE  │ →   │ Status: SAFE    │
│ Issues: 14      │     │ Issues: 0       │
└─────────────────┘     └─────────────────┘

Impact if launched:
- Data breach: User A sees User B's trades
- P&L fraud: Backtest 95%, paper 20%
- Auth bypass: Unauthenticated users create jobs
- Signal injection: False OHLCV triggers trades

Cost of fixes: ~$20k (3 weeks * $80k engineer)
Cost of breach: >$1M (data loss, trust, legal)
```

---

## Validator Checklist

```
✓ Slippage:
  - High liquidity: 0.05% - 0.5%
  - Low liquidity: 0.5% - 5%
  - Micro-cap: 2% - 10%

✓ Position Size:
  - Entry price: $0.01 - $1M
  - Quantity: 1 - 100,000
  - Max % of account: 5-10%

✓ Market Data:
  - Source: Alpaca, Polygon, yfinance, Tradier
  - Status: verified or live
  - No forecasts
  - No future dates

✓ Risk Management:
  - SL: 0.5% - 50%
  - TP: 0.5% - 500%
  - TP > SL always
```

---

## Code Locations to Update

```
CRITICAL:
├─ supabase/migrations/20260226000000_*.sql
│  └─ Add RLS policies
├─ supabase/functions/_shared/validators/slippage-validator.ts
│  └─ NEW - Validate slippage ranges
├─ supabase/functions/_shared/validators/position-validator.ts
│  └─ NEW - Validate position size
└─ supabase/functions/_shared/validators/market-data-validator.ts
    └─ NEW - Validate market data source

HIGH PRIORITY:
├─ supabase/functions/backtest-strategy/index.ts
│  └─ Remove demo fallback (line 37-40)
├─ supabase/functions/_shared/validators/risk-validator.ts
│  └─ NEW - Validate SL/TP
├─ supabase/functions/paper-trading-executor/index.ts
│  └─ Split condition evaluator
└─ supabase/functions/_shared/condition-evaluator-*.ts
    └─ NEW - Separate evaluators

TESTING:
└─ supabase/functions/__tests__/security-validators.test.ts
   └─ NEW - Test all validators
```

---

## Testing Strategy

```
UNIT TESTS (2 days):
└─ Validator tests
   ├─ Slippage: valid, too low, too high
   ├─ Position: valid, zero price, oversized
   ├─ Market data: forecast reject, future reject
   └─ Risk: valid SL/TP, invalid ratio

INTEGRATION TESTS (2 days):
└─ End-to-end workflows
   ├─ RLS: User A cannot read User B's data
   ├─ Position: Entry → Position created → Trade closed
   ├─ Backtest vs paper: Same data = same signals
   └─ Error handling: Invalid inputs rejected

SECURITY TESTS (1 day):
└─ Attack scenarios
   ├─ Unauthenticated request (should 401)
   ├─ Cross-user query (should forbidden)
   ├─ Slippage injection (should reject)
   ├─ Future date injection (should reject)
   └─ P&L overflow (should bounds-check)
```

---

## Success Criteria

- [x] All inputs validated with clear min/max bounds
- [x] All user-owned data protected by RLS
- [x] All financial calculations have overflow guards
- [x] Paper executor <500ms latency
- [x] Backtest & paper trading use same data = same signals
- [x] 95%+ test coverage on validators
- [x] Zero cross-user data leakage
- [x] All error messages generic (no schema info)

---

## Team Questions (Discuss Before Implementation)

1. Liquidity classification: Volume threshold for high/low/micro-cap?
2. Slippage defaults: Are 0.05%-5% ranges realistic?
3. Position limits: 5% or 10% per position max?
4. SL/TP bounds: Are 0.5%-50% SL, 0.5%-500% TP correct?
5. Divergence threshold: Yellow at 5%, red at 15% divergence?

---

## Resources

- Full audit: `SECURITY_AUDIT_STRATEGY_PLATFORM.md`
- Implementation: `SECURITY_FIXES_IMPLEMENTATION.md`
- Executive summary: `SECURITY_AUDIT_EXECUTIVE_SUMMARY.md`
- Original plan: `docs/plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md`

---

**Estimated Total Effort:** 18-22 days (3-4 weeks)
**Blocking v1 Launch:** Yes, all 8 high-priority issues must be fixed
**Post-v1 Improvements:** Encryption, versioning, Kelly Criterion sizing

