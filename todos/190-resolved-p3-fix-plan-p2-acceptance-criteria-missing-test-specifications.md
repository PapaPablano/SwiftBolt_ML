---
status: resolved
priority: p3
issue_id: "190"
tags: [plan-review, live-trading, testing, documentation]
dependencies: []
---

# Fix Plan: P2 acceptance criteria missing test specifications — no test matrix for verifying fixes

## Problem Statement

The plan's P2 acceptance criteria are stated as checkbox goals without specifying how to verify them without a live broker. Each criterion needs a test fixture that controls what broker APIs return, a specific action to take, and a concrete assertion. Without these, implementers have no guidance on how to confirm that the fixes are working correctly before deploying to production.

## Findings

**Spec-Flow Analyzer (GAP-P3-1):**

Three key P2 acceptance criteria that lack test specifications:

**1. SL/TP recalculated from fill price (#119):**

Current acceptance criterion: "SL and TP prices are calculated from the actual fill price, not the bar close price."

Missing test specification:
- **Setup:** Set `TRADESTATION_USE_SIM=true`, configure a strategy with SL=2%, TP=4%
- **Action:** Submit an execution request, let `pollOrderFill` return `{ fillPrice: 150.00 }` (not the bar close of 149.50)
- **Assert:** `live_trading_positions.stop_loss_price = 150.00 * 0.98 = 147.00` (not `149.50 * 0.98 = 146.51`)
- **How to control:** Mock `pollOrderFill` to return a deterministic fill price different from `current_price`

**2. FK delete policies are RESTRICT (#121):**

Current acceptance criterion: "Both FK delete policies prevent cascading deletes."

Missing test specification:
- **Setup:** Insert a test user, a `live_trading_positions` row for that user, a `live_trading_trades` row for that position
- **Action:** Attempt `DELETE FROM auth.users WHERE id = $test_user_id` in a transaction
- **Assert:** FK constraint violation error raised (not silent cascade)
- **Verification SQL:** Add to `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`

**3. CHECK constraints on `live_trading_trades` (#122):**

Current acceptance criterion: "INSERT with invalid data fails CHECK constraint."

Missing test specification:
- **Setup:** Attempt to INSERT a `live_trading_trades` row with `pnl = 2000000` (exceeds bounds)
- **Assert:** CHECK constraint violation error
- **Note:** Since trades are immutable (trigger blocks UPDATE), testing CHECKs requires attempt INSERT with bad data — not possible via the normal executor path. A direct SQL test is needed in the deployment verification script.

## Proposed Solution

Add a "Test Matrix" section to the plan's acceptance criteria, specifying for each P2 item: (a) system state to set up, (b) action to take, (c) what to assert. Add corresponding SQL verification queries to `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`.

## Acceptance Criteria

- [x] Plan includes test specifications for SL/TP fill price calculation verification
- [x] Plan includes test specifications for FK RESTRICT verification (SQL DELETE test)
- [x] Plan includes test specifications for CHECK constraint verification (bad-data INSERT test)
- [x] Verification queries added to `docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P3-1) during plan review. Acceptance criteria without test specifications leave implementers guessing how to confirm fixes work before production deployment.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
