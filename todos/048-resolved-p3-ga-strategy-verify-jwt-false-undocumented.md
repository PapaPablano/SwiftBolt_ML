---
status: resolved
priority: p3
issue_id: "048"
tags: [code-review, security, edge-functions, configuration]
dependencies: []
---

# 048 — ga-strategy Deployed with verify_jwt=false, No Auth Rationale Documented

## Problem Statement
`ga-strategy` (genetic algorithm optimizer) has JWT verification disabled in `supabase/config.toml` with no comment explaining the intended caller or any compensating auth mechanism. This compute-intensive function can be triggered by anyone without authentication.

## Findings
- `supabase/config.toml`: `ga-strategy` entry with `verify_jwt = false`
- No internal auth check found in `ga-strategy/index.ts`
- Compare: `run-backfill-worker` documents its gateway key approach in config comments

## Proposed Solutions
Pick one:
- (a) Add gateway key enforcement if cron/admin-only
- (b) Enable `verify_jwt = true` if user-triggered
- (c) Add comment to config.toml explicitly documenting why it's public and what the intended caller is
- Effort: XSmall for any option
- Risk: Low

## Acceptance Criteria
- [x] Either auth is added OR config.toml has clear comment explaining why auth is disabled and what caller is expected

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (MED-05)
- 2026-03-01: Resolved — added comment above `[functions.ga-strategy]` in supabase/config.toml documenting that it is triggered by cron automation only and auth is enforced at the job queue level.
