---
status: ready
priority: p2
issue_id: "063"
tags: [code-review, simplicity, plan-amendment]
dependencies: []
---

# 063 — Plan Phase 1 + 5 Over-Engineered: Simplify Auth and Deploy Flow

## Problem Statement

The Simplicity Reviewer identified several over-engineered elements across Phases 1 and 5:

**Phase 1 (Auth):**
- AuthContext + AuthGate as two separate components when `@supabase/supabase-js` already manages session state
- Magic link as a secondary option adds redirect handling complexity
- A dedicated login page is unnecessary for a single-user research workstation

**Phase 5 (Deploy):**
- Full-page PaperTradingReviewScreen with risk assessment for paper (fake) money
- Both compact status widget AND full dashboard tab (redundant)
- `strategyTranslator.ts` as a separate file for what could be a single function

## Findings

- **Simplicity Reviewer:** "~500 LOC saved by replacing AuthContext+AuthGate with useAuth hook, review screen with confirm dialog, and cutting status widget"
- **Architecture Strategist:** "Both compact + full dashboard is the right architecture" (disagrees on cutting widget)

## Proposed Solutions

### Option A: Aggressive Simplification
- Replace AuthContext+AuthGate with `useAuth.ts` hook (~30 LOC)
- Email/password only, no magic link
- Replace review screen with confirmation dialog
- Cut status widget, keep only dashboard tab
- **Pros:** ~500 LOC saved, simpler mental model
- **Cons:** Less polished UX
- **Effort:** Small
- **Risk:** Low

### Option B: Moderate Simplification (Recommended)
- Keep AuthContext (lightweight, standard React pattern) but inline login as a modal
- Email/password only, no magic link
- Replace full review screen with a compact review modal (strategy name, conditions summary, SL/TP, confirm/cancel)
- Keep status widget (it's small and useful for quick glance)
- **Pros:** Good UX, reasonable scope
- **Cons:** Status widget adds polling
- **Effort:** Medium
- **Risk:** Low

## Technical Details

**Files affected by simplification:**
- `frontend/src/contexts/AuthContext.tsx` (keep or replace with hook)
- `frontend/src/components/AuthGate.tsx` (eliminate or inline as modal)
- `frontend/src/components/PaperTradingReviewScreen.tsx` (eliminate or simplify to modal)
- `frontend/src/components/PaperTradingStatusWidget.tsx` (keep or cut)

## Acceptance Criteria

- [ ] Auth flow works for paper trading
- [ ] Deploy flow has a confirmation step before execution
- [ ] Dashboard tab is wired in App.tsx
- [ ] Chosen simplification level documented in plan

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Simplicity reviewer vs Architecture strategist tension on widget |
