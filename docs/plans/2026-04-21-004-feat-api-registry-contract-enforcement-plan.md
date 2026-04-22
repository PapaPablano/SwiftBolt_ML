---
title: "feat: API registry and response contract enforcement"
type: feat
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md
---

# feat: API Registry and Response Contract Enforcement

## Overview

Create a centralized API registry that catalogs every Edge Function's contract (method, auth model, response schema, consumers) and add response schema validation so breaking changes are caught in CI before they reach production. Builds on the existing `api-contract-tests.yml` workflow (which already validates chart, user-refresh, and data-health schemas via `ajv-cli`) and the `AUTH_MATRIX.md` created in PR #32.

## Problem Frame

The backend has 56 Edge Functions with no unified catalog of their contracts. Response shapes are defined inline across function files with no shared schema. The existing `api-contract-tests.yml` validates 3 endpoints — the other 54 are uncovered. When a function's response shape changes, there's no mechanism to notify client callers before the change ships. (see origin: `docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md`, Phase 2)

## Requirements Trace

- R5. Create an API registry manifest cataloging every Edge Function: name, HTTP method, auth model, consumers, deploy workflow, data dependencies
- R6. Add JSON Schema (Draft-7) response definitions to `_shared/schemas/` for priority client-facing endpoints (chart, strategies, options-chain, quotes, futures-roots), validated by ajv-cli in CI. Remaining client-facing functions deferred to future iterations
- R7. Establish API versioning for client-facing endpoints (additive changes are non-breaking per CLAUDE.md)
- R8. Auth matrix — DONE (docs/AUTH_MATRIX.md, PR #32)

## Scope Boundaries

- **In scope:** Registry manifest, response schemas for client-facing functions, CI validation, versioning policy
- **Out of scope:** Runtime validation middleware (ship schemas + CI first, runtime later), TypeScript-to-Swift code generation (manual sync for now), function consolidation (Phase 4), CI workflow consolidation (Phase 3)
- **Non-goal:** Schemas for internal/cron-only functions — they have no external consumers to break

### Deferred to Separate Tasks

- Runtime response validation in Edge Functions: future iteration after schemas stabilize
- TypeScript-to-Swift automated code generation: future iteration
- Phase 3 CI/CD consolidation: separate plan
- Phase 4 function consolidation: separate plan

## Context & Research

### Relevant Code and Patterns

- `supabase/functions/_shared/chart-types.ts` — Existing chart response type definitions (TypeScript interfaces)
- `supabase/functions/_shared/types/multileg.ts` — Multi-leg strategy types
- `supabase/functions/_shared/response.ts` — Standardized helpers: `jsonOk`, `jsonError`, `jsonUnauthorized`, `jsonNotFound`, `jsonServerError` (not yet universally adopted)
- `supabase/functions/_shared/cors.ts` — CORS + legacy `jsonResponse` helpers
- `.github/workflows/api-contract-tests.yml` — Existing contract test workflow using `ajv-cli` + `ajv-formats`. Currently validates chart, user-refresh, data-health endpoints with JSON Schema Draft-7. Also checks Swift model compatibility.
- `docs/AUTH_MATRIX.md` — Complete auth matrix for all 56 functions (created in PR #32)

### Institutional Learnings

- **API contract rule** (CLAUDE.md): "Any breaking change to a function's response requires a PR review of all affected callers. Additive changes (new optional fields) do not require caller updates."
- **apikey vs Bearer** (from `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md`): `apikey` header = anon key (routing), `Authorization` = user JWT (auth). Response schemas must document which auth model the endpoint expects.

## Key Technical Decisions

- **JSON Schema (Draft-7) as the schema format:** The existing `api-contract-tests.yml` already uses `ajv-cli` with Draft-7 schemas. Extending this is simpler than introducing Zod or another runtime library. JSON Schema is language-neutral — useful for both TypeScript (ajv) and Swift (JSONSchema validation) consumers.
- **Registry as a single YAML manifest:** A machine-readable `supabase/functions/registry.yaml` file that CI can validate against the actual function directories. If a function exists on disk but not in the registry, CI fails. If a client-facing function in the registry lacks a schema file, CI warns.
- **Schemas only for client-facing functions:** Internal/cron functions (run-backfill-worker, ingest-live, etc.) have no external callers to break. Schema effort should focus on the ~25 client-facing functions identified in AUTH_MATRIX.md.
- **Versioning as response header, not URL path:** Add `X-API-Version: 1` header to all client-facing responses. Breaking changes increment the version. Clients can check this header to detect incompatible responses. No URL-path versioning — keeps the current URL structure intact.
- **Extend existing contract test workflow:** Don't create a new workflow. Add schema files and registry validation to the existing `api-contract-tests.yml`.

## Open Questions

### Resolved During Planning

- **Schema format?** JSON Schema Draft-7 — matches existing `ajv-cli` infrastructure in `api-contract-tests.yml`.
- **Where do schemas live?** `supabase/functions/_shared/schemas/` directory, one file per client-facing function (e.g., `chart.schema.json`, `strategies.schema.json`).
- **Registry format?** YAML manifest at `supabase/functions/registry.yaml` — machine-readable, CI-validatable.
- **How does AUTH_MATRIX.md relate?** The registry subsumes it for machine-readable data. AUTH_MATRIX.md remains as the human-readable reference. The registry's auth fields should be consistent with AUTH_MATRIX.md.

### Deferred to Implementation

- Exact JSON Schema definitions for each endpoint — derive from reading actual response shapes during implementation
- Whether `response.ts` `jsonOk()` should accept a schema parameter for optional runtime validation (future iteration)
- Priority ordering of which client-facing functions to schema-ify first

## Implementation Units

- [x] **Unit 1: Create registry manifest with all 56 functions**

**Goal:** Create a machine-readable YAML manifest cataloging every Edge Function.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Create: `supabase/functions/registry.yaml`

**Approach:**
- One entry per function with fields: `name`, `method` (GET/POST/PUT/DELETE), `auth` (jwt/gateway-key/anon/optional-bearer), `consumers` (client/cron/internal), `schema` (path to schema file or null), `description` (one-line purpose)
- Derive auth and consumer data from `docs/AUTH_MATRIX.md`
- Mark client-facing functions as `schema: null` initially — Unit 2 fills these in
- Internal/cron functions get `schema: null` permanently (no external consumers)

**Patterns to follow:**
- `docs/AUTH_MATRIX.md` — source for auth model and consumer type per function

**Test expectation:** none — pure data file with no behavioral logic. Validation comes in Unit 3.

**Verification:**
- Every directory in `supabase/functions/` (excluding `_shared/` and `tests/`) has a corresponding entry in `registry.yaml`
- Auth fields match `AUTH_MATRIX.md`

---

- [x] **Unit 2: Add JSON Schema files for priority client-facing functions**

**Goal:** Create JSON Schema (Draft-7) response definitions for the highest-traffic client-facing endpoints.

**Requirements:** R6

**Dependencies:** Unit 1 (registry exists to reference schema paths)

**Files:**
- Create: `supabase/functions/_shared/schemas/chart.schema.json`
- Create: `supabase/functions/_shared/schemas/strategies.schema.json`
- Create: `supabase/functions/_shared/schemas/options-chain.schema.json`
- Create: `supabase/functions/_shared/schemas/quotes.schema.json`
- Create: `supabase/functions/_shared/schemas/futures-roots.schema.json`
- Update: `supabase/functions/registry.yaml` — fill in `schema:` paths for these functions

**Approach:**
- For each function: read the actual response construction in `index.ts`, derive the JSON Schema from the response shape
- Start with the 5 highest-traffic client-facing functions (chart, strategies, options-chain, quotes, futures-roots)
- Use `"additionalProperties": true` to allow additive changes without breaking validation (per CLAUDE.md convention)
- For the chart endpoint: create the new `chart.schema.json` as the canonical schema. Unit 3 will retire the inline schema from `api-contract-tests.yml` — do NOT extend the inline version
- Include `required` properties for fields that are part of the contract, `optional` for enrichment fields

**Execution note:** Read each function's response construction before writing the schema — do not guess the shape from types alone.

**Patterns to follow:**
- Existing JSON Schema definitions in `.github/workflows/api-contract-tests.yml` (inline schemas for chart, user-refresh, data-health)
- `supabase/functions/_shared/chart-types.ts` — TypeScript type reference for chart response

**Test scenarios:**
- Happy path: `ajv validate --spec=draft7 -s chart.schema.json -d sample-chart-response.json` passes
- Happy path: Response with additional optional fields still validates (additionalProperties: true)
- Error path: Response missing a required field fails validation
- Edge case: Empty bars array validates (bars is required but can be empty)
- Edge case: Null values in optional fields validate

**Verification:**
- Each schema file validates against a sample response from its endpoint
- `ajv-cli` validates all 5 schemas without errors
- Registry entries for these 5 functions have `schema:` paths filled in

---

- [x] **Unit 3: Add registry validation to CI**

**Goal:** Extend `api-contract-tests.yml` to validate the registry against the actual function directories and validate response schemas.

**Requirements:** R5, R6

**Dependencies:** Units 1 and 2

**Files:**
- Modify: `.github/workflows/api-contract-tests.yml`

**Approach:**
- Add a job step that compares `registry.yaml` entries against `ls supabase/functions/` — fail if a function directory exists without a registry entry
- Add a job step that validates all `*.schema.json` files in `_shared/schemas/` are valid JSON Schema Draft-7
- Move the existing inline schema definitions (chart, user-refresh, data-health) from the workflow file to `_shared/schemas/` and reference them from the workflow
- Keep the existing smoke test and Swift compatibility checks unchanged

**Patterns to follow:**
- Existing `api-contract-tests.yml` structure — add steps within the existing job rather than creating a new workflow

**Test scenarios:**
- Happy path: All functions in registry, all schemas valid — CI passes
- Error path: New function directory added without registry entry — CI fails with clear message
- Error path: Schema file with invalid JSON Schema syntax — CI fails
- Edge case: `_shared/` and `tests/` directories are excluded from the registry check
- Integration: PR that modifies a function response AND its schema — both validate

**Verification:**
- CI passes on the current state (all functions registered, all schemas valid)
- Adding a new function directory without updating the registry causes CI failure
- Adding a malformed schema file causes CI failure

---

- [x] **Unit 4: Add API version header to client-facing responses**

**Goal:** Add `X-API-Version: 1` header to all client-facing Edge Function responses to enable version detection.

**Requirements:** R7

**Dependencies:** None (parallel with Units 1-3)

**Files:**
- Modify: `supabase/functions/_shared/response.ts` — add version header to `jsonOk` and `jsonError`
- Modify: `supabase/functions/_shared/cors.ts` — add version header to `corsResponse`

**Approach:**
- Add `X-API-Version: 1` to the default headers in `corsResponse()` and `jsonOk()`/`jsonError()` in `response.ts`
- This requires two independent edits: (1) add the header to the base headers inside `corsResponse()` in cors.ts, and (2) add it to the headers spread in `jsonOk()`/`jsonError()` in response.ts (which does NOT route through corsResponse)
- Document the versioning policy: version increments only on breaking response shape changes. Additive fields are non-breaking.
- Functions using legacy inline response construction (not yet migrated to `response.ts`) will not get the header until they're migrated — this is acceptable for Phase 2

**Patterns to follow:**
- Existing header addition pattern in `corsResponse()` — the `additionalHeaders` parameter

**Test scenarios:**
- Happy path: `GET /chart?symbol=AAPL&timeframe=d1` response includes `X-API-Version: 1` header
- Happy path: Error responses also include the version header
- Edge case: Functions using legacy inline `new Response()` don't get the header (expected, documented)
- Integration: Both React and Swift clients can read the header (verify one client during implementation)

**Verification:**
- `curl -I` to chart endpoint shows `X-API-Version: 1` in response headers
- Error responses (400, 401, 500) also include the header

---

- [x] **Unit 5: Update AUTH_MATRIX.md with registry cross-reference**

**Goal:** Add a note to AUTH_MATRIX.md pointing to the machine-readable registry and keep both in sync.

**Requirements:** R5

**Dependencies:** Unit 1 (registry exists)

**Files:**
- Modify: `docs/AUTH_MATRIX.md`

**Test expectation:** none — documentation update with no behavioral change.

**Verification:**
- AUTH_MATRIX.md references `supabase/functions/registry.yaml` as the machine-readable source
- Both documents agree on auth model for all functions

## System-Wide Impact

- **Interaction graph:** The registry and schemas are consumed by CI only (no runtime impact). The `X-API-Version` header is additive to all responses via shared helpers.
- **Error propagation:** Schema validation failures in CI block deployment — this is intentional. No runtime error path changes.
- **API surface parity:** The version header appears in responses to both React and Swift clients. Schema definitions are language-neutral (JSON Schema) and consumable by both.
- **Unchanged invariants:** No response shapes are changed. No function behavior is modified. All changes are additive (new files, new CI steps, new header).

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Registry goes stale when new functions are added | CI validation step (Unit 3) fails on unregistered functions — enforces freshness |
| JSON Schema too strict — breaks on legitimate additive changes | Use `additionalProperties: true` on all schemas |
| X-API-Version header conflicts with Supabase gateway headers | Supabase gateway does not use `X-API-Version` — no conflict. Prefix with `X-` per convention. |
| Existing inline schemas in api-contract-tests.yml diverge from new _shared/schemas/ files | Unit 3 moves inline schemas to _shared/schemas/ — single source of truth |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md](docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md) — Phase 2 (R5-R8)
- Auth matrix: `docs/AUTH_MATRIX.md` (PR #32)
- Existing contract tests: `.github/workflows/api-contract-tests.yml`
- Existing types: `supabase/functions/_shared/chart-types.ts`
- Response helpers: `supabase/functions/_shared/response.ts`, `supabase/functions/_shared/cors.ts`
