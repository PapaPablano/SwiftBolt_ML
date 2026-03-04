---
status: resolved
priority: p3
issue_id: "165"
tags: [plan-review, live-trading, typescript, code-quality]
dependencies: []
---

# Fix Plan Phase 6.1: Add `Math.floor()` to exponential backoff for clarity

## Problem Statement

The Phase 6.1 exponential backoff uses `delay = Math.min(delay * 1.5, MAX_DELAY)`, which produces non-integer millisecond values (e.g., 1687.5). `setTimeout` truncates these internally, so there is no runtime impact — but the floating-point values appear in log messages as `"waiting 1687.5ms"`, which looks unintentional.

## Findings

**TypeScript Reviewer (P3):**

The sequence `500 → 750 → 1125 → 1687.5 → 2531.25 → ...` produces fractional ms values. The plan's comment shows `1687` (already truncated), suggesting the author intended integer values. Adding `Math.floor()` makes the intent explicit and prevents fractional values in log output.

## Proposed Solution

```typescript
delay = Math.floor(Math.min(delay * 1.5, MAX_DELAY));
// 500 → 750 → 1125 → 1687 → 2531 → 3796 → 5000
```

## Acceptance Criteria

- [x] `Math.floor()` added to backoff calculation (or equivalent)
- [x] Log messages show integer millisecond values

## Work Log

- 2026-03-03: Finding from kieran-typescript-reviewer (P3) during plan review.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
