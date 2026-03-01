---
status: pending
priority: p2
issue_id: "040"
tags: [code-review, performance, edge-functions, api-design]
dependencies: []
---

# 040 — strategies GET Returns Unbounded Results With SELECT *

## Problem Statement
`strategies/index.ts` GET handler queries `strategy_user_strategies` with no `.limit()` call and `SELECT *`, returning the entire strategy list including full JSONB `config` blobs. At scale (50+ strategies with complex condition trees) this creates an unbounded payload per request.

## Findings
- `supabase/functions/strategies/index.ts` lines 112-118: no `.limit()`, `select("*")`
- `config` column is JSONB containing full condition tree — large per strategy
- No `offset` or cursor parameter for pagination

## Proposed Solutions
List endpoint: narrow select + add pagination:
```typescript
.select("id, name, is_active, paper_trading_enabled, created_at, updated_at")
.order("updated_at", { ascending: false })
.limit(50)
.range(offset, offset + 49)
```
Load full `config` only on single-strategy GET.
- Effort: Small (1 hour)
- Risk: Low

## Acceptance Criteria
- [ ] List endpoint returns max 50 strategies per request
- [ ] `offset` query param supported for pagination
- [ ] List response excludes `config` JSONB blob
- [ ] Single strategy GET still returns full config

## Work Log
- 2026-03-01: Identified by performance-oracle review agent
