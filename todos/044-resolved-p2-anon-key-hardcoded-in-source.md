---
status: pending
priority: p2
issue_id: "044"
tags: [code-review, security, frontend, credentials]
dependencies: []
---

# 044 — Supabase Anon Key Hardcoded in TradingViewChart.tsx

## Problem Statement
`frontend/src/components/TradingViewChart.tsx` contains a hardcoded Supabase anon key string literal. While anon keys are publishable, hardcoding prevents zero-downtime key rotation and sets a bad precedent — sensitive values should always come from environment variables. The correct pattern is used in `backtestService.ts`.

## Findings
- `TradingViewChart.tsx` line ~30: `const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'` (hardcoded)
- `backtestService.ts` line 6: correctly uses `import.meta.env.VITE_SUPABASE_ANON_KEY`
- Hardcoded key cannot be rotated without a code change and redeployment

## Proposed Solutions
One-line fix:
```typescript
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';
```
- Effort: XSmall (5 minutes)
- Risk: None

## Acceptance Criteria
- [ ] No hardcoded JWT strings in any frontend source file
- [ ] All anon key references use `import.meta.env.VITE_SUPABASE_ANON_KEY`
- [ ] `.env.local.template` documents all required env vars

## Work Log
- 2026-03-01: Identified by API contract review agent
