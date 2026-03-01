---
status: pending
priority: p2
issue_id: "034"
tags: [code-review, performance, edge-functions, caching]
dependencies: []
---

# 034 — technical-indicators getCachedIndicators Always Returns null

## Problem Statement
`technical-indicators/index.ts` has a `getCachedIndicators` stub that always returns `null`, forcing every request to trigger a full 500-bar indicator calculation on the FastAPI backend. With 30-second polling and multiple concurrent users this becomes the highest-frequency compute load in the system.

## Findings
- `supabase/functions/technical-indicators/index.ts` lines 64-77: `return null; // For now, we'll skip database caching`
- `MemoryCache` infrastructure exists in `_shared/cache/memory-cache.ts` but is not wired
- Every 30-second chart poll fires a full indicator recalculation through FastAPI

## Proposed Solutions

### Option A: Wire MemoryCache singleton (Recommended)
```typescript
const cache = new MemoryCache<TechnicalIndicatorsResponse>({ maxAge: 60_000 });
async function getCachedIndicators(symbol: string, timeframe: string) {
  return cache.get(`${symbol}:${timeframe}`);
}
```
- Effort: Small (1-2 hours)
- Risk: Low

### Option B: indicator_values table (persistent cache)
Write results to `indicator_values` table; read back if within TTL.
- Effort: Medium
- Risk: Low

## Recommended Action
Option A for immediate 90% reduction; Option B for persistence across cold starts.

## Technical Details
- **Affected files:** `supabase/functions/technical-indicators/index.ts`, `supabase/functions/_shared/cache/memory-cache.ts`

## Acceptance Criteria
- [ ] Repeated requests within 60s served from cache
- [ ] FastAPI indicator calculation rate reduced significantly for active symbols
- [ ] Cache invalidated after TTL

## Work Log
- 2026-03-01: Identified by performance-oracle review agent
