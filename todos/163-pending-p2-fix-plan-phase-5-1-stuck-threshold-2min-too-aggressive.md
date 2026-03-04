---
status: pending
priority: p2
issue_id: "163"
tags: [plan-review, live-trading, state-machine, reliability]
dependencies: []
---

# Fix Plan Phase 5.1: 2-minute stuck position threshold is too aggressive — institutional learnings recommend 5 minutes

## Problem Statement

The Phase 5.1 recovery scan uses a `STUCK_POSITION_THRESHOLD_MS = 2 * 60 * 1000` (2 minutes). The institutional learnings document (`docs/LIVE_TRADING_EXECUTOR_INSTITUTIONAL_LEARNINGS.md`, Section 8) explicitly recommends a 5-minute threshold for orphaned position detection. A 2-minute threshold risks triggering emergency closes on positions that are still in legitimate mid-execution states during broker-side slowdowns.

## Findings

**Learnings Researcher (Gotcha B):**

From `docs/LIVE_TRADING_EXECUTOR_INSTITUTIONAL_LEARNINGS.md` Section 8 (stuck-position recovery pattern):

> Orphaned `pending_entry` detection: query for positions older than 5 minutes

The Edge Function invocation cycle is typically 60 seconds. During market volatility or broker slowdowns, the entire processing chain can take 30–90 seconds. A 2-minute threshold means a position created during a slow cycle could be emergency-closed before the next normal cycle even has a chance to detect and process it. The 5-minute window (as per the documented pattern) provides a safety buffer for:

- Broker API latency spikes during market opens/closes
- TradeStation maintenance windows with extended response times
- Multiple slow cycles in succession

## Proposed Solution

Update Phase 5.1 to use a 5-minute threshold OR make it configurable via environment variable:

```typescript
// Use 5 minutes to match institutional learnings pattern and allow for broker slowdowns
// Set STUCK_POSITION_THRESHOLD_SECONDS env var to override (min: 180, max: 600)
const thresholdSeconds = Math.min(
  Math.max(
    parseInt(Deno.env.get("STUCK_POSITION_THRESHOLD_SECONDS") ?? "300", 10),
    180,  // minimum: 3 minutes
  ),
  600,    // maximum: 10 minutes
);
const STUCK_POSITION_THRESHOLD_MS = thresholdSeconds * 1000;
```

The env var approach allows operational tuning without code changes if 5 minutes proves too conservative for a specific strategy's execution profile.

## Acceptance Criteria

- [ ] Stuck position threshold updated to 5 minutes (300,000ms) OR made configurable
- [ ] Plan references institutional learnings document for the 5-minute recommendation
- [ ] Minimum threshold bounded to prevent overly aggressive values being set via env var

## Work Log

- 2026-03-03: Finding from learnings-researcher (Gotcha B) during plan review.
