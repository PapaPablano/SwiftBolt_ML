---
status: pending
priority: p3
issue_id: "055"
tags: [code-review, security, input-validation, edge-functions, chart]
dependencies: []
---

# 055 — Unvalidated barLimit and optionsLimit Allow Unbounded Response Sizes

## Problem Statement
`chart/index.ts` accepts `bars_limit` and `options_limit` query parameters with no upper bound. A caller supplying `bars_limit=10000000` causes a slice of millions of rows — potentially exhausting Edge Function memory and creating extremely large JSON responses.

## Findings
- `chart/index.ts` lines 284-289: `barLimit` has no max cap
  ```typescript
  const barLimit = barLimitParam ? Number(barLimitParam) : allBars.length;
  allBars.slice(Math.max(0, barOffset), Math.max(0, barOffset) + Math.max(0, barLimit));
  ```
- `optionsLimitParam` also has no upper bound
- Negative or NaN values handled by `Math.max(0, ...)` but no maximum enforced
- `strategy-backtest/index.ts` has a similar pattern on pagination params

## Proposed Solutions
Add validation at the top of the handler:
```typescript
const MAX_BAR_LIMIT = 2000;
const MAX_OPTIONS_LIMIT = 100;
const barLimit = Math.min(MAX_BAR_LIMIT, Math.max(1, Number(barLimitParam) || MAX_BAR_LIMIT));
const optionsLimit = Math.min(MAX_OPTIONS_LIMIT, Math.max(1, Number(optionsLimitParam) || 10));
```
- Effort: XSmall (20 minutes)
- Risk: None

## Acceptance Criteria
- [ ] `bars_limit` capped at 2000
- [ ] `options_limit` capped at 100
- [ ] Negative values clamped to 1
- [ ] Non-numeric values default to sensible defaults
- [ ] Valid requests unaffected

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (MED-02)
