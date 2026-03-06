---
status: pending
priority: p3
issue_id: "066"
tags: [code-review, testing, plan-amendment]
dependencies: []
---

# 066 — Plan Missing Test Strategy Per Phase

## Problem Statement

The plan mentions 131 existing unit tests but does not include a test strategy for new code. Each phase should specify test targets and minimum coverage expectations.

## Findings

- **Architecture Strategist:** "Each phase should specify test file targets and minimum test count expectations"

## Proposed Solutions

Add a "Testing" subsection to each phase:
- Phase 1: useAuth hook tests (sign in, sign out, token refresh, session persistence)
- Phase 2: backtestService mapping tests for new fields, fallback behavior when fields absent
- Phase 3: TradeRegionPrimitive unit tests (coordinate calculation, color logic, cleanup)
- Phase 4: Table rendering tests, drawdown computation tests
- Phase 5: Strategy translator tests, deploy flow integration tests

## Acceptance Criteria

- [ ] Each phase in plan has testing subsection
- [ ] Test file paths specified per phase
- [ ] Minimum test count expectations set

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Architecture Strategist finding |
