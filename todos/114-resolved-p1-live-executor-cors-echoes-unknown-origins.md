---
status: pending
priority: p1
issue_id: "114"
tags: [code-review, live-trading, security, cors]
dependencies: []
---

# CORS helper echoes unknown origins back as allowed — should reject instead

## Problem Statement

In `supabase/functions/_shared/cors.ts` lines 85–87, when an origin is not in the allowed list, the code falls through and echoes `allowed[0]` (the first allowed origin) back in the `Access-Control-Allow-Origin` header. This means any unknown origin still gets a CORS header allowing the first whitelisted domain, rather than receiving no CORS header (which would cause the browser to block the request). While the origin isn't echoed directly, the fallback header reveals the first allowed origin and may allow unintended cross-origin access depending on client handling.

## Findings

Security Sentinel FINDING-04.

## Proposed Solutions

Option A (Recommended): For unknown origins, return `null` or omit the `Access-Control-Allow-Origin` header entirely. The browser will block the cross-origin request as intended. Only echo the request's origin if it appears in the allowlist. Effort: Small.

## Acceptance Criteria

- [ ] Unknown origins receive no `Access-Control-Allow-Origin` header
- [ ] Known/allowed origins receive their origin echoed back
- [ ] CORS preflight for unknown origins returns a non-2xx status or omits the CORS header
