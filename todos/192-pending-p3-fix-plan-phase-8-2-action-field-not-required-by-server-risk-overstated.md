---
status: pending
priority: p3
issue_id: "192"
tags: [plan-review, live-trading, api-design, documentation]
dependencies: []
---

# Fix Plan Phase 8.2: Execute `action` field is not required by server — plan overstates it as a bug fix

## Problem Statement

Phase 8.2's problem statement says the execute API is "missing the `action` field," framing it as a functional bug. But the executor's POST handler does not require an `action` field for execution — any POST body containing `symbol` and `timeframe` that does not match `close_position`, `save_broker_token`, or `disconnect_broker` is treated as an execution request. Adding `action: "execute"` is a defensive improvement for clarity and forward-compatibility, not a bug fix. Overstating it risks implementers treating it as P1 when it is actually P3 housekeeping.

## Findings

**Spec-Flow Analyzer (GAP-P3-3):**

Executor handler routing (lines 1389–1402 of `index.ts`):
```typescript
const body = await req.json();
const { action, symbol, timeframe } = body;

switch (action) {
  case "close_position": ...
  case "save_broker_token": ...
  case "disconnect_broker": ...
  default:
    // Falls through to execution cycle — no action field required
    const { symbol, timeframe } = body;
    if (symbol && timeframe) {
      return await executeLiveTradingCycle(...);
    }
}
```

Current `strategiesApi.ts` execute call (lines 53–58):
```typescript
execute: (symbol: string, timeframe: string, token: string) =>
  invokeFunction('live-trading-executor', {
    method: 'POST',
    body: { symbol, timeframe },  // ← no action field, works fine
    token,
  }),
```

This works correctly today. Adding `action: "execute"` would improve:
- Code readability (intent is explicit)
- Forward-compatibility (if the `default` branch is removed in a future refactor)
- Log clarity (action field appears in structured logs)

But it does not fix a broken behavior. The plan's Phase 8.2 problem statement for todo #124 should be corrected to read: "defensive improvement — add explicit `action: 'execute'` field to execute API call for clarity" rather than "API call is missing required field."

## Proposed Solution

Correct Phase 8.2's problem statement from "missing required field" to "defensive improvement for clarity and forward-compatibility." Downgrade the urgency framing accordingly. The code change itself is correct and should still be made — just accurately characterized.

## Acceptance Criteria

- [ ] Plan's Phase 8.2 description corrected to reflect that `action` is not required today
- [ ] Phase 8.2 characterized as defensive improvement, not bug fix
- [ ] Code change (add `action: "execute"`) still included — just with accurate rationale

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P3-3) during plan review. The implementation is correct; the problem statement framing needed correction to avoid unnecessary urgency.
