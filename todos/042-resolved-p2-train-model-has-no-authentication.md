---
status: pending
priority: p2
issue_id: "042"
tags: [code-review, security, edge-functions]
dependencies: []
---

# 042 — train-model Edge Function Has No Authentication

## Problem Statement
`supabase/functions/train-model/index.ts` triggers ML model training jobs with no auth check. Any unauthenticated caller can trigger expensive training operations on the ML backend, causing cost overruns and potential model interference.

## Findings
- `train-model/index.ts`: no JWT verification, no gateway key check
- Function invokes Python ML training pipeline (expensive, long-running)
- No rate limiting applied
- Other admin functions like `run-backfill-worker` use gateway key enforcement — this function does not

## Proposed Solutions

### Option A: Gateway key enforcement (Recommended — admin-only trigger)
Follow the `run-backfill-worker` pattern: check `X-SB-Gateway-Key` header against `SB_GATEWAY_KEY` env var. Fail-close if key not configured.
- Effort: Small (1 hour)
- Risk: Low

### Option B: Enable verify_jwt = true (user-triggered training)
Set `verify_jwt = true` and add admin role check inside function.
- Effort: Small
- Risk: Low

## Recommended Action
Option A (training is an admin/cron operation, not user-triggered).

## Acceptance Criteria
- [ ] train-model rejects requests without valid gateway key (returns 401)
- [ ] Authorized requests continue to work
- [ ] Fail-close if SB_GATEWAY_KEY not configured

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (HIGH-04)
