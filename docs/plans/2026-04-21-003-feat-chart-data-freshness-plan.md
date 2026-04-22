---
title: "feat: Surface chart data freshness to clients"
type: feat
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md
---

# feat: Surface Chart Data Freshness to Clients

## Overview

The data freshness infrastructure largely exists — `ohlc_bars_v2` tracks `fetched_at`/`updated_at`/`data_status`, `ingest-live` writes m1 bars via pg_cron every minute, and the chart Edge Function already computes staleness (`ageMinutes`, `isStale`, `FRESHNESS_SLA_MINUTES`). What's missing is surfacing this freshness data explicitly in the chart response so clients can display staleness indicators, and tightening the intraday SLA to match the 60-second freshness target.

## Problem Frame

Chart data can be stale during market hours but clients have no way to know. The chart Edge Function computes freshness internally but the response doesn't include explicit `last_updated` timestamps or a clear `stale` boolean that clients can use. The intraday ingestion via GitHub Actions runs every 5 minutes for higher timeframes while pg_cron runs `ingest-live` every minute for m1 bars. The freshness SLA constants (`FRESHNESS_SLA_MINUTES`) may not reflect the 60-second target for intraday data. (see origin: `docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md`, Phase 1)

## Requirements Trace

- R1. OHLCV bars must be no more than 120 seconds (2 minutes) stale during market hours for watched symbols (for m15 timeframe, the tightest client-facing SLA; pg_cron ingests m1 bars every minute but m1 is not directly served by the chart endpoint)
- R3. The `chart` Edge Function response must include explicit freshness metadata: `last_updated` timestamp, `is_stale` boolean, and `age_seconds`
- R4. The chart function must never trigger a synchronous refresh-on-read that blocks the response — return stale data with staleness indicator

Note: R2 (push-based ingestion) is already largely satisfied by pg_cron running `ingest-live` every minute for m1 bars. The GitHub Actions cron (now 5min) handles higher timeframes. No new ingestion mechanism is needed.

## Scope Boundaries

- **In scope:** Enrich chart response freshness metadata, tighten SLA constants, add client-side staleness indicator
- **Out of scope:** New ingestion mechanisms (pg_cron already runs every minute), database schema changes (columns already exist), full API registry (Phase 2), CI consolidation (Phase 3)
- **Non-goal:** Sub-minute ingestion for higher timeframes (d1, w1) — only m1/m15 need tight SLA

### Deferred to Separate Tasks

- Phase 2 (API Registry & Contracts): separate plan
- Phase 3 (CI/CD Consolidation): separate plan

## Context & Research

### Relevant Code and Patterns

- `supabase/functions/chart/index.ts` — Main chart endpoint. Already computes `ageMinutes`, `isStale`, `FRESHNESS_SLA_MINUTES`. Has a `freshness` field in the response object. Uses `get_chart_data_v2` RPC with fallback to direct query.
- `supabase/functions/ingest-live/index.ts` — Writes m1 bars every minute via pg_cron. UPSERT to `ohlc_bars_v2` with `data_status: 'live'`, `is_intraday: true`.
- `supabase/migrations/20260105000000_ohlc_bars_v2.sql` — Table already has `fetched_at`, `updated_at` (trigger-managed), `data_status` (live/verified/provisional) columns.
- `.github/workflows/intraday-ingestion.yml` — Runs Python scripts every 5 minutes for m15/h1 timeframes during market hours. Separate from the pg_cron m1 pipeline.
- `FRESHNESS_SLA_MINUTES` constant map in chart function: `{ m15: 30, m30: 60, h1: 120, h4: 480, d1: 1440, w1: 10080 }` — m1 is not listed (m1 is not in `VALID_TIMEFRAMES` either — chart endpoint doesn't serve m1 directly).

### Institutional Learnings

- **API contract rule** (CLAUDE.md): "Any breaking change to a function's response requires a PR review of all affected callers." Adding new fields to the chart response is additive (non-breaking), but changing the shape of the existing `freshness` field would be breaking.

## Key Technical Decisions

- **Enrich existing `freshness` field rather than adding a sibling:** The chart response already has a `freshness` object. Add `last_updated`, `is_stale`, and `age_seconds` to it rather than creating a new top-level `data_freshness` field. This is additive and non-breaking per CLAUDE.md convention.
- **Drop m1 SLA — m1 is not a valid chart timeframe:** `VALID_TIMEFRAMES` is `[m15, m30, h1, h4, d1, w1]` — the chart endpoint rejects `timeframe=m1` with 400. m1 bars are consumed by partial candle synthesis, not served directly. No SLA entry needed for m1. The tightest client-facing SLA is m15.
- **No new ingestion mechanism:** pg_cron already runs `ingest-live` every minute for m1 bars. The GitHub Actions 5-minute cron handles higher timeframes. The brainstorm's R2 (push-based ingestion) is already satisfied by existing infrastructure — no architectural change needed.
- **Client staleness indicator is a frontend concern:** The chart response provides the data; how it's displayed (badge, color, tooltip) is a client decision. This plan adds the backend data; client UI changes are out of scope.

## Open Questions

### Resolved During Planning

- **Does the chart response already have a freshness field?** Yes — a `freshness` object exists in the response. Its current shape needs verification during implementation to determine what fields it already contains.
- **Is pg_cron running ingest-live every minute?** Yes — confirmed in `ingest-live/index.ts` comments and pg_cron configuration. This satisfies R2 without new infrastructure.
- **What SLA is appropriate for m1?** 2 minutes (1-minute pg_cron interval + processing buffer). Tighter than the brainstorm's 60-second target but realistic for the existing cron mechanism.

### Deferred to Implementation

- Exact current shape of the `freshness` object in the chart response — read the code to determine what already exists before adding fields
- Whether `get_chart_data_v2` RPC returns `fetched_at`/`updated_at` or if those need to be queried separately
- Whether the Swift and React clients already read the `freshness` field (grep during implementation)

## Implementation Units

- [x] **Unit 1: Add m1 SLA and enrich freshness response metadata**

**Goal:** Add m1 to the SLA map and include explicit `last_updated`, `is_stale`, `age_seconds` in the chart response's freshness object.

**Requirements:** R1, R3, R4

**Dependencies:** None

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Test: `supabase/functions/chart/index_test.ts` (create if absent)

**Approach:**
- Read the existing `freshness` field construction in the response builder (already computes `ageMinutes`, `slaMinutes`, `isWithinSla` from `lastActualBarTs`). Enrich it with these additional fields:
  - `last_updated`: ISO 8601 timestamp from `lastActualBarTs` (the most recent bar's `ts` — this is the only timestamp available; the RPC does not return `updated_at`/`fetched_at`)
  - `is_stale`: boolean, true when `ageMinutes` exceeds the SLA for the requested timeframe (mirrors existing `isWithinSla` inverted)
  - `age_seconds`: integer, `ageMinutes * 60` rounded
  - `sla_seconds`: integer, `slaMinutes * 60`
- All inputs (`lastActualBarTs`, `ageMinutes`, `slaMinutes`) are already computed as local variables — no new queries needed.
- Confirm the JSON field naming convention (camelCase vs snake_case) matches the existing chart response fields before shipping.

**Patterns to follow:**
- Existing `FRESHNESS_SLA_MINUTES` map and `ageMinutes`/`isStale` computation in chart/index.ts
- Additive response field pattern per CLAUDE.md API contract rules

**Test scenarios:**
- Happy path: Chart response for m15 timeframe includes `freshness.last_updated`, `freshness.is_stale`, `freshness.age_seconds`, `freshness.sla_seconds`
- Happy path: When data is fresh (age < SLA), `is_stale` is false
- Happy path: When data is stale (age > SLA), `is_stale` is true and `age_seconds` reflects actual staleness
- Edge case: No bars returned (empty chart) — freshness fields should be null or absent, not error
- Edge case: m15 uses tightened SLA, d1 uses 1440-minute SLA — verify different timeframes get correct SLA
- Integration: Smoke test via `GET /chart?symbol=AAPL&timeframe=m15` returns freshness metadata in response

**Verification:**
- `GET /chart?symbol=AAPL&timeframe=m15` response includes `freshness.is_stale`, `freshness.last_updated`, `freshness.age_seconds`
- `GET /chart?symbol=AAPL&timeframe=d1` also includes freshness metadata with different SLA
- No breaking changes to existing response fields (additive only)

---

- [x] **Unit 2: Tighten m15 SLA and add freshness to intraday timeframes**

**Goal:** Reduce the m15 freshness SLA from 30 minutes to 10 minutes to match the 5-minute GitHub Actions cron, and ensure m15/h1 freshness is computed the same way as m1.

**Requirements:** R1

**Dependencies:** Unit 1 (freshness metadata pattern established)

**Files:**
- Modify: `supabase/functions/chart/index.ts`

**Approach:**
- Update `FRESHNESS_SLA_MINUTES` map: change `m15: 30` to `m15: 10` (2x the 5-minute cron interval as buffer).
- Verify the freshness computation applies to all timeframes equally (the `ageMinutes` logic should already be generic).

**Test scenarios:**
- Happy path: m15 chart with data older than 10 minutes shows `is_stale: true`
- Happy path: m15 chart with data younger than 10 minutes shows `is_stale: false`
- Edge case: h1 SLA remains at 120 minutes (unchanged)

**Verification:**
- `FRESHNESS_SLA_MINUTES` map includes `m15: 10, m30: 60, h1: 120, h4: 480, d1: 1440, w1: 10080` (m30 preserved unchanged, m15 tightened from 30 to 10)

---

- [x] **Unit 3: Document freshness architecture**

**Goal:** Create a concise reference document explaining the data freshness pipeline so future developers understand the ingestion and staleness detection flow.

**Requirements:** Supports all R1-R4 by making the architecture legible

**Dependencies:** Units 1-2 (documents the final state)

**Files:**
- Create: `docs/DATA_FRESHNESS.md`

**Approach:**
- Document the two ingestion paths:
  - pg_cron → `ingest-live` → m1 bars every minute
  - GitHub Actions → Python scripts → m15/h1/d1 bars every 5 minutes
- Document the SLA map and how staleness is computed
- Document the chart response freshness metadata fields
- Note the `data_status` column values (`live`, `verified`, `provisional`) and when each is set

**Test expectation:** none — pure documentation with no behavioral change.

**Verification:**
- Document covers both ingestion paths, SLA thresholds, and response format
- A new developer can understand why chart data might be stale and where to look

## System-Wide Impact

- **Interaction graph:** Chart Edge Function response shape changes (additive). React frontend and SwiftUI client both consume this response. New fields are additive — no breaking change.
- **Error propagation:** Freshness computation failure should not block the chart response. If freshness metadata can't be computed, omit the fields rather than returning an error.
- **State lifecycle risks:** None — reading existing timestamps, no new writes.
- **API surface parity:** Both clients receive the same freshness metadata. How they display it is their concern.
- **Unchanged invariants:** The `chart` endpoint response shape is additive only. All existing fields remain unchanged. The `ingest-live` Edge Function is not modified. The GitHub Actions ingestion workflow is not modified (already at 5min).

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `get_chart_data_v2` RPC doesn't return `updated_at` | Confirmed: RPC returns only bar `ts`. All freshness fields use `lastActualBarTs` (already computed). No fallback needed. |
| Existing `freshness` field has unexpected shape | Read actual response during implementation before modifying. Additive changes only. |
| m15 SLA tightened to 10min but GH Actions cron is 5min | Two consecutive cron failures would trigger staleness. Acceptable — staleness indicator is informational, not blocking. |
| Pre-existing: `p_limit` param passed to RPC but not defined | Out of scope for this plan but implementer should be aware. PostgREST may ignore unknown params in non-strict mode. |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md](docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md) — Phase 1 (R1-R4)
- Chart endpoint: `supabase/functions/chart/index.ts`
- Ingestion: `supabase/functions/ingest-live/index.ts`, `.github/workflows/intraday-ingestion.yml`
- Table schema: `supabase/migrations/20260105000000_ohlc_bars_v2.sql`
