---
date: 2026-04-22
topic: docker-fastapi-simplification
---

# Docker/FastAPI Architecture Documentation

## Problem Frame

The app has a hybrid architecture: Supabase Edge Functions for serverless API + Docker FastAPI for heavy Python ML computation. 10 Edge Functions proxy to FastAPI via `callFastApi()`, 5 FastAPI endpoints are unique (no Edge equivalent), and 2 have partial overlap. This works but is undocumented — developers don't know which features require Docker running.

## Requirements

**Documentation**
- R1. Add a "Local Development" section to AGENTS.md documenting the Docker/FastAPI relationship: when Docker is needed, what it provides, how Edge Functions fallback works
- R2. Document the 3 tiers of functionality: (1) works without Docker (core chart, options, news), (2) enhanced with Docker (backtesting, walk-forward, Greeks use heavier Python compute), (3) Docker-only (WebSocket streaming, binary forecasts)
- R3. Update `docker-compose.yml` with inline comments explaining the architecture

**Cleanup**
- R4. Remove the `localhost:8000` connection refused console noise — add a one-time silent health check on app launch; suppress repeated connection-refused logs if FastAPI is not running
- R5. Mark the 5 unique FastAPI features in the API registry (`registry.yaml`) so the registry reflects which functions need Docker

## Scope Boundaries

- **In scope:** Documentation, console noise reduction, registry annotation
- **Out of scope:** Removing FastAPI, migrating computation to Edge Functions, changing the proxy pattern
- **Non-goal:** Making Docker required — the app should continue to work without it

## Key Decisions

- **Keep the hybrid pattern:** Edge Functions for serverless routing + FastAPI for heavy ML compute is the right architecture. It just needs documentation.
- **Silence connection-refused noise, don't fix it:** The Swift client trying `localhost:8000` first and falling back is correct behavior. Just suppress the console spam.

## Next Steps

-> `/ce:plan` for structured implementation planning
