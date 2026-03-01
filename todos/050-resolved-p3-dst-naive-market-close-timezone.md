---
status: pending
priority: p3
issue_id: "050"
tags: [code-review, correctness, edge-functions]
dependencies: []
---

# 050 — DST-Naive Timezone Handling in data-validation.ts Market Close Calculation

## Problem Statement
`_shared/data-validation.ts` calculates market close time with a hardcoded `-5` UTC offset (EST). During EDT (UTC-4, approx. March–November), market close is calculated as 21:00 UTC instead of the correct 20:00 UTC. Data write locks apply one hour late during the ~8 months of EDT.

## Findings
- `_shared/data-validation.ts` lines 153-163: `etOffset = -5` with comment acknowledging approximation
- EDT runs approximately March–November (~8 months)
- During EDT: post-market write lock triggers at wrong time

## Proposed Solutions
Use Temporal API (available in Deno):
```typescript
const nowInET = Temporal.Now.zonedDateTimeISO('America/New_York');
const marketCloseET = nowInET.with({ hour: 16, minute: 0, second: 0, nanosecond: 0 });
const isAfterClose = Temporal.ZonedDateTime.compare(nowInET, marketCloseET) > 0;
```
- Effort: Small (1 hour)
- Risk: Low

## Acceptance Criteria
- [ ] Market close calculation correct during both EST (UTC-5) and EDT (UTC-4)
- [ ] Tests cover both summer and winter timestamps
- [ ] No hardcoded UTC offset

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (LOW-03)
