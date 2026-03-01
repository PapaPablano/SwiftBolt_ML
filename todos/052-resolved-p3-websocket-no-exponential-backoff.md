---
status: pending
priority: p3
issue_id: "052"
tags: [code-review, performance, frontend, websocket, resilience]
dependencies: []
---

# 052 — WebSocket Reconnection Uses Fixed 5s Delay (Thundering Herd Risk)

## Problem Statement
`frontend/src/hooks/useWebSocket.ts` reconnects after exactly 5 seconds on every disconnect regardless of failure count. When the backend restarts, all connected clients retry simultaneously, creating a thundering herd that can overwhelm the WebSocket server on startup.

## Findings
- `useWebSocket.ts` lines 86-91: `setTimeout(() => connect(), 5000)` — fixed delay, no backoff
- No attempt counter, no jitter
- 8 symbols × N concurrent users all retry at the same instant on backend restart

## Proposed Solutions
```typescript
const attempt = reconnectAttemptsRef.current++;
const delay = Math.min(30_000, 1_000 * Math.pow(2, attempt)) + Math.random() * 1_000;
reconnectTimeoutRef.current = setTimeout(connect, delay);
// Reset on successful connect:
reconnectAttemptsRef.current = 0;
```
- Effort: XSmall (30 minutes)
- Risk: None

## Acceptance Criteria
- [ ] Reconnect delay doubles on each failure (1s, 2s, 4s, 8s... max 30s)
- [ ] Random jitter (0-1s) prevents lockstep retries
- [ ] Attempt counter resets on successful connection

## Work Log
- 2026-03-01: Identified by performance-oracle review agent
