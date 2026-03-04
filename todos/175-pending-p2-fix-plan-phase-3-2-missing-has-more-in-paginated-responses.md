---
status: pending
priority: p2
issue_id: "175"
tags: [plan-review, live-trading, agent-native, api-design, pagination]
dependencies: []
---

# Fix Plan Phase 3.2: Paginated responses missing `has_more` boolean — agent pagination risks off-by-one errors

## Problem Statement

The Phase 3.2 fix correctly replaces `positions?.length ?? 0` with Supabase's `{ count: "exact" }` to return accurate `total` counts in positions, trades, and summary GET responses. However, requiring agents to compute `has_more = (offset + limit) < total` themselves is unnecessary and introduces a failure surface: an off-by-one or sign error in the agent's computation leads to either stopping early (missing data) or infinite loops on the final page. Adding `has_more: boolean` to the response costs one line and eliminates the ambiguity.

## Findings

**Agent-Native Reviewer (P2-Finding 3):**

Current response shape (after Phase 3.2 fix):
```typescript
{ positions: data ?? [], total: count ?? 0, offset, limit }
```

An agent paginating must compute: `const hasMore = offset + limit < total`

This is simple arithmetic, but:
- An agent with a stale `total` (from a previous call made before new positions were created) could compute an incorrect `has_more`
- An agent library that rounds or truncates could produce off-by-one results on the final page
- The response already contains all the information needed to compute this — returning it eliminates all ambiguity

**Correct response shape (one additional field):**
```typescript
{
  positions: data ?? [],
  total: count ?? 0,
  offset,
  limit,
  has_more: (offset + limit) < (count ?? 0),  // ← add this
}
```

This should be applied consistently to all three paginated endpoints:
- `GET ?action=positions`
- `GET ?action=trades`
- `GET ?action=summary` (if paginated)

## Proposed Solution

Amend Phase 3.2 in the plan to include `has_more: boolean` in all paginated response shapes. This is a zero-cost addition (computed from values already present in the response) that makes agent pagination deterministic.

## Acceptance Criteria

- [ ] `has_more: boolean` added to positions endpoint response
- [ ] `has_more: boolean` added to trades endpoint response
- [ ] `has_more: boolean` added to summary endpoint response (if paginated)
- [ ] `has_more` correctly evaluates to `false` on the final page (when `count` rows have been returned)

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P2-Finding 3) during plan review.
