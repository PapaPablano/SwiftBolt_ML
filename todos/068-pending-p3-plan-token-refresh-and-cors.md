---
status: pending
priority: p3
issue_id: "068"
tags: [code-review, security, cors, session-management]
dependencies: ["059"]
---

# 068 — Plan Missing Token Refresh Handling + Wildcard CORS

## Problem Statement

Two security gaps in the plan:

1. **Token refresh:** AuthContext handles `SIGNED_OUT` but not `TOKEN_REFRESHED`. Supabase JWTs expire (default 1 hour). Long paper trading sessions will fail with 401 after expiry.

2. **Wildcard CORS:** `paper-trading-executor` uses `Access-Control-Allow-Origin: *`, allowing any website to make cross-origin requests. Combined with the auth fix (059), this allows any website to make authenticated requests if the user visits it while logged in (mitigated by localStorage token storage, but still a defense-in-depth gap).

## Findings

- **Security Sentinel:** MEDIUM — token refresh missing, wildcard CORS
- **Architecture Strategist:** "Add TOKEN_REFRESHED handling in AuthContext"
- **Learnings Researcher:** JWT session handling gotcha — stale tokens cause 401 cascades

## Proposed Solutions

- Add `TOKEN_REFRESHED` event handling to AuthContext/useAuth hook
- Restrict CORS origins to production domain + localhost for dev
- Check `session.expires_at` before deploy flow submission

## Acceptance Criteria

- [ ] Auth state updates on token refresh (no stale JWT in API calls)
- [ ] CORS restricted to known frontend origins
- [ ] Deploy flow checks token freshness before submission

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Security Sentinel + Learnings Researcher findings |
