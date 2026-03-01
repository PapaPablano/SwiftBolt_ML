---
status: pending
priority: p3
issue_id: "047"
tags: [code-review, architecture, api-design]
dependencies: ["028"]
---

# 047 — No API Versioning Strategy Across Edge Functions

## Problem Statement
50+ Edge Functions have no versioning strategy. When a function's response contract changes, all callers break simultaneously with no migration path. Historical evidence: three chart functions coexist because there is no mechanism to deprecate one without breaking callers.

## Findings
- No version prefix in function names (only platform-level `/functions/v1/` prefix)
- `chart-data-v2` named to imply versioning but `chart-data` was never retired
- No deprecation headers, sunset dates, or migration guides documented
- No OpenAPI specs for any function

## Proposed Solutions

### Option A: Semantic versioning in function names
Convention: retire old function name, deploy `{function}-v{major}` for breaking changes. Old version returns 301 redirect for 6 months then 410.
- Effort: Process change (no immediate code work)

### Option B: Version header routing
`X-API-Version: 2` header; function branches internally.
- Effort: Medium per function
- Risk: Complexity

### Option C: Document contracts + enforce change review (Recommended now)
Treat Edge Function response shapes as API contracts. Any breaking change requires a PR review and a parallel callers-update PR.
- Effort: XSmall (just process + one doc)
- Risk: None

## Recommended Action
Option C now. Option A when chart consolidation (#028) is complete.

## Acceptance Criteria
- [ ] API contract document listing all function response shapes exists
- [ ] Process for reviewing breaking changes established in CLAUDE.md
- [ ] At minimum: `chart-data-v2` retired after chart consolidation

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
