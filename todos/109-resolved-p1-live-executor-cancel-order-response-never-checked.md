---
status: pending
priority: p1
issue_id: "109"
tags: [code-review, live-trading, typescript, financial-safety, error-handling]
dependencies: []
---

# `cancelOrder` never validates HTTP response — silent failure on real-money cleanup

## Problem Statement

The `cancelOrder` function (lines 266–277 of `live-trading-executor/index.ts`) calls TradeStation's DELETE endpoint but never checks `response.ok`. It is typed to return `Promise<void>` and swallows any broker-side rejection silently. This function is called in two critical paths: (1) cleanup after fill timeout (line 836), (2) cleanup after DB insert failure (line 819). In both cases a silent cancel failure leaves an open position at the broker with no SL/TP protection and no DB record tracking it.

## Findings

TypeScript reviewer P1-5. This is a real-money safety issue — an untracked open position at the broker is the worst possible outcome.

## Proposed Solutions

Option A (Recommended): Make `cancelOrder` return `Promise<boolean>` and throw/return false on non-OK responses. Both call sites should handle failure by logging a structured alert that includes the orderId, position details, and timestamp. Effort: Small.

Option B: Make `cancelOrder` throw on HTTP errors and update callers to catch and log with structured error context. Effort: Small.

## Acceptance Criteria

- [ ] `cancelOrder` checks `response.ok` and logs structured error if cancel fails
- [ ] Both callers (timeout cleanup and DB failure cleanup) handle cancel failure and produce an observable log event
- [ ] A failed cancel does NOT silently proceed — it should either retry or escalate to an alert
