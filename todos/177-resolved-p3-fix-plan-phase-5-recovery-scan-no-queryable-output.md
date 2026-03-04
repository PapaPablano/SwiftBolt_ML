---
status: resolved
priority: p3
issue_id: "177"
tags: [plan-review, live-trading, agent-native, observability, reliability]
dependencies: []
---

# Fix Plan Phase 5: Recovery scan produces no queryable output — agent cannot detect or audit emergency closes

## Problem Statement

The Phase 5 `recoverStuckPositions` function runs at the start of every execution cycle and performs emergency closes on positions stuck in `pending_bracket`. This is a critical safety mechanism for real-money positions. However, the proposed implementation only writes `console.error` logs when a recovery occurs. There is no structured output that an agent (or operator) can query to detect whether a recovery ran, which positions were affected, or why they were closed. A position emergency-closed by the recovery scan looks identical to a normal position close from an agent's perspective.

## Findings

**Agent-Native Reviewer (P3-Finding 5):**

A user watching the live trading dashboard would see a position suddenly close with `close_reason = "emergency_close"`. An agent has no way to detect this happened without polling all closed positions and correlating timestamps — an expensive and fragile approach.

The agent-native principle requires that any action the executor takes on real-money positions be queryable. This is especially important for recovery actions where the executor overrides the strategy's normal exit logic.

**Minimum viable addition — filter on existing endpoint:**

The simplest approach requires no new table: add `close_reason` as a filter on the trades endpoint and document that agents should check for emergency closes after each cycle:

```
GET ?action=trades&close_reason=emergency_close&since=<ISO timestamp>
```

**More robust addition — recovery events table:**

```sql
CREATE TABLE live_trading_recovery_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id),
  position_id  UUID REFERENCES live_trading_positions(id),
  action       TEXT NOT NULL CHECK (action IN ('emergency_close', 'cancelled', 'advanced_to_open')),
  reason       TEXT NOT NULL,
  recovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

With a corresponding endpoint:
```
GET ?action=recovery_events&since=<ISO timestamp>
```

## Proposed Solution

At minimum, add a note to Phase 5 in the plan documenting the observability gap: `recoverStuckPositions` produces no queryable output and agents must poll for positions with `close_reason = 'emergency_close'` to detect recovery events.

If time permits in the same PR, add `close_reason` as a server-side filter on the trades GET endpoint (parallel to the `?status=` filter being added in Phase 8.4).

The `live_trading_recovery_events` table approach is a follow-up and does not need to block this PR.

## Acceptance Criteria

- [x] Phase 5 in the plan includes a note documenting that recovery events are not queryable via the GET API
- [x] Plan flags as a follow-up: add `close_reason` filter to trades endpoint OR add `live_trading_recovery_events` table
- [x] If `close_reason` filter is added in this PR, document it in Phase 8.4 alongside the other filter additions

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P3-Finding 5) during plan review. Recovery scan is a critical safety mechanism with no audit trail visible to agents.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
