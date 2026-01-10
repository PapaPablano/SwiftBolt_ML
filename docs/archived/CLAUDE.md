# Stock Analysis Platform - Claude Code Instructions

## Project Overview
macOS SwiftUI app for stock/futures/options analysis with ML-powered forecasts. Backend on Supabase (Postgres + Edge Functions). Python ML pipeline.

## Tech Stack
- **Backend**: Supabase Edge Functions (TypeScript/Deno), Postgres
- **Client**: Swift 5.9+, SwiftUI, macOS 14+
- **ML**: Python 3.11+, scikit-learn, pandas
- **Data Providers**: Finnhub, Massive API

## Project Structure
```
/backend          - Supabase Edge Functions
/client-macos     - SwiftUI macOS app
/ml               - Python ML pipeline
/infra            - Docker, deployment
/docs             - Architecture docs
```

## Coding Standards
- Swift: MVVM, async/await, @StateObject/@ObservedObject
- TypeScript: Strict mode, explicit types
- Python: Type hints, ruff for linting
- All: Small focused files (<300 lines), clear naming

## Current Phase
Phase 0 - Project Setup & Foundations

## Key Docs
- docs/master_blueprint.md - Full architecture
- docs/blueprint_checklist.md - Implementation tracker

## Rules
1. Always check the checklist before starting work
2. Mark checklist items [x] when complete
3. Commit after each working feature
4. Don't skip phases
5. Ask for clarification on ambiguous tasks
