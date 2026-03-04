---
status: pending
priority: p2
issue_id: "183"
tags: [plan-review, live-trading, frontend, ux, api-design]
dependencies: []
---

# Fix Plan Phase 8.1: `{ success: false }` HTTP 200 from `close_position` not caught in frontend — silent failure

## Problem Statement

The Phase 8.1 fix adds error toast feedback for failed close operations. However, the executor can return HTTP 200 with `{ success: false, error: "..." }` — the frontend's `invokeFunction` only checks `res.ok` (HTTP status), not the response body's `success` field. A `{ success: false }` response does not throw, the `catch` block is never reached, `fetchAll()` runs, the position remains open, and the user sees no indication that the close failed.

## Findings

**Spec-Flow Analyzer (GAP-P2-1):**

Current `handleClose` in `LiveTradingDashboard.tsx` lines 122–133:
```typescript
const handleClose = async (positionId: string) => {
  setClosingId(positionId);
  try {
    await liveTradingApi.closePosition(positionId, session.access_token);
    await fetchAll();  // <- runs on success
  } catch (err) {
    console.error('[LiveTradingDashboard] Close failed:', err);
    // show toast
  } finally {
    setClosingId(null);
  }
};
```

The executor's `close_position` handler (lines 1094–1098 of `index.ts`) can return:
```typescript
return corsResponse({ success: false, error: result.error }, 200, origin);
// ← HTTP 200, so invokeFunction does NOT throw
```

When this happens:
1. `invokeFunction` resolves successfully (HTTP 200)
2. The return value is `{ success: false, error: "..." }`
3. `handleClose` does not inspect the return value
4. `catch` is never reached — no toast shown
5. `fetchAll()` runs — position still appears in the list
6. User assumes their click did nothing (or retries)

**Fix:**

```typescript
const handleClose = async (positionId: string) => {
  setClosingId(positionId);
  try {
    const result = await liveTradingApi.closePosition(positionId, session.access_token);
    if (!result.success) {
      throw new Error(result.error ?? 'Close position failed');
    }
    await fetchAll();
    showToast({ type: 'success', message: 'Position closed' });
  } catch (err) {
    console.error('[LiveTradingDashboard] Close failed:', err);
    showToast({ type: 'error', message: err.message ?? 'Failed to close position' });
  } finally {
    setClosingId(null);
  }
};
```

This check should also be applied to all other `invoke`-based operations that can return `{ success: false }` with HTTP 200: `save_broker_token`, `disconnect_broker`, `recover_positions` (when added).

## Proposed Solution

Amend Phase 8.1 in the plan to explicitly check the response body's `success` field in addition to HTTP status, and show the toast in both the HTTP error case and the `{ success: false }` case.

## Acceptance Criteria

- [ ] `handleClose` checks `result.success` after successful HTTP response
- [ ] `{ success: false }` response shows the same error toast as an HTTP error
- [ ] Pattern applied consistently to all executor POST operations in the frontend
- [ ] Plan notes that the executor can return HTTP 200 with `success: false`

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-1) during plan review. The Phase 8.1 toast addition is correct but incomplete — it only handles HTTP errors, not application-level `{ success: false }` responses.
