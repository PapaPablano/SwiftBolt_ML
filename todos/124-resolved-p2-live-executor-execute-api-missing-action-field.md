---
status: pending
priority: p2
issue_id: "124"
tags: [code-review, live-trading, frontend, api-contract, typescript]
dependencies: []
---

# `liveTradingApi.execute` sends no `action` field — relies on implicit fall-through routing

## Problem Statement

In `frontend/src/api/strategiesApi.ts` (lines 53–58), `liveTradingApi.execute` sends `{ symbol, timeframe }` with no `action` field. The executor dispatches on `body.action` at lines 1274, 1321, 1378 of `live-trading-executor/index.ts`. The execute call works only because it falls through all named action checks to the default "execute trading cycle" path at lines 1389–1409. This is an implicit contract — if a future developer adds an action branch above the fall-through, this call silently routes to the wrong handler.

## Findings

TypeScript reviewer P2-5.

## Proposed Solutions

**Option A (Recommended):** Add `action: 'execute'` to the request body in `liveTradingApi.execute`, and add a corresponding named branch in the executor's action dispatch. Effort: Small — one-line change in each file.

## Acceptance Criteria

- [ ] `liveTradingApi.execute` includes `action: 'execute'` in the request body
- [ ] The executor has a named branch for `action === 'execute'` rather than relying on fall-through
- [ ] All other action values (`close_position`, `summary`, etc.) are still handled by their existing named branches
