---
title: Backend API Improvements
type: feat
status: active
date: 2026-02-28
oorigin: docs/brainstorms/2026-02-28-backend-api-improvements-brainstorm.md
---

# Backend API Improvements

## Overview
We aim to streamline the backend data pipeline for indicator and chart values, improving response latency and ensuring real‑time consistency while leveraging Supabase’s Postgres for caching. The goal is to provide a robust, low‑latency API surface that the React frontend and SwiftUI client can consume reliably.

## Problem Statement / Motivation
- **Latency**: Current indicator/chart API responses are slower than desired, impacting user experience on the dashboard.
- **Stale Data**: Indicators and chart values can become outdated between requests, leading to inconsistent UI states.
- **Throughput**: High‑frequency data ingestion and concurrent API requests strain the Edge Functions.
- **Feature Expansion**: Additional fields (e.g., forecast confidence, volatility bands) may be required in the future.

## Proposed Solution
We will implement a **dedicated cache table with TTL logic** in Supabase Postgres, accessed by Edge Functions. The plan is:
1. Create `indicator_cache` table storing JSONB of indicator/chart data and a `last_updated` timestamp.
2. Edge Function checks the timestamp; if older than 30 s, recomputes via database queries or ML pipeline and updates the row.
3. The API returns cached data when fresh, otherwise triggers a refresh.
4. Optional WebSocket/Server‑Sent Events can be added later for real‑time updates.

### Rationale
- **Simplicity**: No external cache service; uses existing Postgres infrastructure.
- **Flexibility**: JSONB allows evolving schema without altering table structure.
- **Control**: TTL logic in the function gives fine‑grained refresh control.

## Technical Considerations
- **Cache Invalidation**: 30 s TTL; can be tuned via environment variable.
- **Concurrency**: Use `SELECT FOR UPDATE` or a lightweight lock to prevent duplicate refreshes.
- **Data Consistency**: Reads are eventually consistent; if strict consistency is required, consider adding a `version` column and optimistic concurrency checks.
- **Security**: Edge Functions run with Supabase service key; ensure no sensitive data is exposed.
- **Scalability**: Postgres can handle the read load; monitor query performance and add indexes as needed.
- **Extensibility**: JSONB structure can include new fields (e.g., forecast confidence) without schema migrations.

## System‑Wide Impact
- **Interaction Graph**: API call → Edge Function → `indicator_cache` table → ML pipeline (if refresh needed). The function may trigger a background job to recompute indicators.
- **Error Propagation**: Errors in the refresh path should return a 503 with retry guidance; cached data remains available.
- **State Lifecycle Risks**: Stale cache may serve outdated data; TTL mitigates this. Ensure the refresh path handles failures gracefully.
- **API Surface Parity**: Existing `/chart` endpoint will be extended to return cached data; new optional query parameters may expose raw or aggregated values.
- **Integration Test Scenarios**:
  - Request fresh data after TTL expiry and verify recomputation.
  - Simulate concurrent requests to ensure single refresh.
  - Verify that new fields are correctly serialized and returned.

## Acceptance Criteria
- [ ] API returns indicator/chart data within 200 ms for 95% of requests.
- [ ] Cached data is refreshed at most once every 30 s per symbol/timeframe.
- [ ] No duplicate refreshes occur under concurrent load (race‑free).
- [ ] New fields can be added to the JSONB payload without breaking existing consumers.
- [ ] API remains secure; no sensitive data is exposed.

## Success Metrics
- **Latency**: Target <200 ms average response time.
- **Cache Hit Rate**: >90% of requests served from cache.
- **Staleness Window**: <30 s between data updates.
- **Throughput**: Handle ≥10,000 concurrent requests with 99.9% uptime.

## Dependencies & Risks
- **Dependencies**: Supabase Postgres, Edge Functions runtime, ML pipeline functions.
- **Risks**:
  - Cache refresh race conditions if lock not implemented correctly.
  - Postgres performance degradation under heavy read load.
  - Future schema changes may require JSONB updates.

## Open Questions (to resolve before implementation)
1. **Endpoint structure** – single consolidated API or separate endpoints for chart vs indicator data?
2. **Feature expansion** – Which additional fields (forecast confidence, volatility bands) are required now or in the near future?
3. **Data consistency** – Is eventual consistency acceptable, or do we need stricter guarantees?
4. **Real‑time updates** – Should we implement WebSocket/Server‑Sent Events for live chart updates, or rely on polling?

## Sources & References
- **Brainstorm document**: [docs/brainstorms/2026-02-28-backend-api-improvements-brainstorm.md](docs/brainstorms/2026-02-28-backend-api-improvements-brainstorm.md)
- **Supabase Postgres docs**: https://supabase.com/docs/guides/database
- **Edge Functions guide**: https://supabase.com/docs/reference/javascript/functions#edge-functions
- **JSONB usage patterns**: https://www.postgresql.org/docs/current/datatype-json.html
- **Concurrency control in Postgres**: https://www.postgresql.org/docs/current/transaction-iso.html
