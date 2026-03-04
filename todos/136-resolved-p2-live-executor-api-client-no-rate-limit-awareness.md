---
status: pending
priority: p2
issue_id: "136"
tags: [code-review, live-trading, agent-native, rate-limiting, api-client]
dependencies: []
---

# `liveTradingApi` has no rate limit awareness — 429 responses become opaque errors for agents

## Problem Statement

The execute endpoint enforces 10 requests per 60-second window. The `invokeFunction` client in `strategiesApi.ts` (lines 20-25) throws a generic error on any non-OK response and does not inspect the `Retry-After` header or return a structured rate limit error. An agent calling `liveTradingApi.execute` in a polling loop will silently fail after 10 calls with an opaque exception and no indication of how long to wait. The rate limit metadata (10/min window) is not documented anywhere in the client layer.

## Findings

Agent-Native Reviewer, Warning #8.

## Proposed Solutions

Option A (Recommended): In `invokeFunction`, check for `response.status === 429` and extract the `Retry-After` header. Throw (or return) a structured `{ type: "rate_limited", retryAfterSeconds: N }` error that callers can handle gracefully. Document the rate limit in a comment at the `liveTradingApi` definition. Effort: Small.

## Acceptance Criteria

- [ ] A 429 response from `live-trading-executor` surfaces a structured rate limit error (not a generic throw)
- [ ] The error includes `retryAfterSeconds` from the `Retry-After` header
- [ ] `liveTradingApi` has a comment documenting the 10 req/min rate limit
