# Commit Message

```
feat: Add watchlist auto-backfill with UI functions

BREAKING CHANGES:
- Backfill system now automatically triggers for watchlist additions
- Added user-facing functions for manual backfill requests

New Features:
- Automatic 2-year backfill when symbols added to watchlist
- BackfillService.swift: Swift service for UI integration
- BackfillStatusView.swift: SwiftUI view for progress display
- Database functions: request_symbol_backfill, get_symbol_backfill_status
- Trigger: watchlist_auto_backfill_trigger on watchlist_items

Database:
- Created migration 20260109060000_watchlist_auto_backfill.sql
- Automatically seeded 7 existing watchlist symbols (3,661 chunks)
- Added RLS policies for authenticated users

UI Components:
- BackfillStatusView: Full progress display with time estimates
- BackfillProgressRow: Individual timeframe progress bars
- BackfillService: Async/await service layer

Documentation:
- WATCHLIST_BACKFILL.md: Complete integration guide
- README_BACKFILL.md: Updated with watchlist features
- Code examples and UI integration patterns

Symbols Auto-Backfilled:
- AAPL, AMD, AMZN, CRWD, MU, NVDA, PLTR
- Total: 3,661 chunks (7 symbols × 523 days × h1 timeframe)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Files Changed

### Database
- `backend/supabase/migrations/20260109060000_watchlist_auto_backfill.sql` (new)

### Swift Services
- `client-macos/SwiftBoltML/Services/BackfillService.swift` (new)

### Swift Views
- `client-macos/SwiftBoltML/Views/BackfillStatusView.swift` (new)

### Documentation
- `WATCHLIST_BACKFILL.md` (new)
- `README_BACKFILL.md` (updated)

## How to Commit

```bash
git add backend/supabase/migrations/20260109060000_watchlist_auto_backfill.sql
git add client-macos/SwiftBoltML/Services/BackfillService.swift
git add client-macos/SwiftBoltML/Views/BackfillStatusView.swift
git add WATCHLIST_BACKFILL.md
git add README_BACKFILL.md
git add .github/workflows/backfill-cron.yml

git commit -m "feat: Add watchlist auto-backfill with UI functions

- Auto-trigger 2-year backfill when symbols added to watchlist
- Add BackfillService and BackfillStatusView for UI integration
- Seed 7 existing watchlist symbols (3,661 chunks)
- Add user-facing SQL functions for manual requests

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```
