---
status: pending
priority: p2
issue_id: "133"
tags: [code-review, live-trading, agent-native, api-design]
dependencies: []
---

# Positions endpoint has no server-side status filter — agents receive all positions including closed history

## Problem Statement

The `GET ?action=positions` endpoint returns all positions regardless of status. The UI filters to open-only at `LiveTradingDashboard.tsx` lines 117-120 via a client-side `useMemo`. An agent querying positions to decide whether to enter a trade must download the full history (including closed, cancelled, pending positions) and filter client-side. This wastes bandwidth and creates incorrect agent behavior if the agent assumes returned positions are currently open.

## Findings

Agent-Native Reviewer, Warning #5.

## Proposed Solutions

Option A (Recommended): Accept an optional `status` query parameter (comma-separated). Example: `GET ?action=positions&status=open,pending_entry,pending_bracket`. Apply a `.in("status", statusList)` filter when the parameter is present. Default to returning all statuses when absent (preserves backward compatibility). Effort: Small.

## Acceptance Criteria

- [ ] `GET ?action=positions&status=open` returns only open positions
- [ ] `GET ?action=positions&status=open,pending_entry,pending_bracket` returns all active positions
- [ ] Omitting `status` parameter returns all positions (backward compatible)
