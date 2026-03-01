# SwiftBolt ML — Code Review Checklist

Use this checklist when reviewing PRs. All items link to institutional learnings in `INSTITUTIONAL_LEARNINGS_AND_PENDING_ITEMS.md`.

## Security (Must-Pass)

- [ ] **No secrets in git:** `.env`, `Secrets.xcconfig`, API keys not in committed files
- [ ] **Info.plist uses build variables:** `$(SUPABASE_URL)`, not literal values
- [ ] **No string interpolation in JS:** `evaluateJavaScript()` always uses `JSONSerialization`
- [ ] **WKWebView sandbox:** `limitsNavigationsToAppBoundDomains = true` + host whitelist
- [ ] **WeakScriptHandler for JS messages:** Prevents `WKUserContentController` retain cycle
- [ ] **No debug code in production:** All `print()` / `debugPrint()` inside `#if DEBUG`

## Swift Concurrency (High Priority)

- [ ] **All Tasks stored:** Task handles are properties, never fire-and-forget
- [ ] **Previous Task cancelled:** Before creating new Task, cancel the old one
  ```swift
  subscriptionTask?.cancel()  // Cancel before new Task
  subscriptionTask = Task { ... }
  ```
- [ ] **Task.isCancelled checked:** Inside `for await` loops, check `guard !Task.isCancelled`
- [ ] **Subscribe/unsubscribe paired:** View lifecycle or `.task` modifier for cleanup
- [ ] **No default: catch-all in switches:** Enums defined in same module must be exhaustive

## SwiftUI Performance (Medium Priority)

- [ ] **Formatters cached:** `NumberFormatter`, `DateFormatter` at file level, not in view bodies
- [ ] **Locale locked:** Formatters initialized once with fixed locale (e.g., `en_US` for currency)
- [ ] **No allocations in render:** Check `onChange`, `body` property for expensive operations
- [ ] **Debouncing for realtime:** High-frequency events debounced (500ms typical)

## Edge Functions (Medium Priority)

- [ ] **Endpoint is canonical:** No duplicate functions with >70% similarity (see P3 issue #021)
- [ ] **Column selection explicit:** `.select("*")` only when genuinely needed; prefer column lists
- [ ] **One NSViewRepresentable per type:** Never copy-paste Web view wrappers
- [ ] **CORS headers present:** All endpoints return `corsHeaders`
- [ ] **Parameterized queries:** No string concatenation in SQL

## Frontend API Integration (Low-Medium Priority)

- [ ] **Single endpoint per concept:** No N+1 fragments of related data
- [ ] **Cache-first pattern:** Return cached, refresh if stale
- [ ] **No direct vendor calls:** All data goes through Edge Functions

## Database (Low Priority)

- [ ] **Explicit column list:** `.select("id,user_id,...")` not `.select("*")`
- [ ] **Indexed on query filters:** `symbol_id, timeframe, ts` on time-series tables
- [ ] **Walk-forward validation only:** ML validation uses temporal ordering, no lookahead bias
- [ ] **RLS policies enforced:** Server-side authorization on sensitive tables

## Documentation (Low Priority)

- [ ] **CLAUDE.md up-to-date:** Commands, env vars, structure reflect current state
- [ ] **Deprecated functions documented:** If replacing, add notice + redirect
- [ ] **Complex logic has comments:** Edge case handling explained
- [ ] **No outdated todos in code:** FIXME/TODO reference tracking system

---

## Quick Scan (Under 5 minutes)

If you're in a hurry, check these three things:

1. **Secrets:** No API keys, tokens, or base URLs in Info.plist or committed config
2. **Tasks:** All `Task {}` blocks are stored properties; previous task cancelled before new one created
3. **API design:** Endpoints are discoverable; column selection explicit; no duplication

---

## P3 Items to Watch For (Pending Implementation)

### When you see realtime code:
- [ ] Check issue #011: Does the code handle connection drop + reconnect?
- [ ] Is `isLive` indicator exposed to UI?

### When you see strategy/backtest endpoints:
- [ ] Check issue #021: Are you using `backtest-strategy` (canonical) not `strategy-backtest`?
- [ ] Check issue #020: Can agents discover active strategies without DB access?

### When you see WebView to native communication:
- [ ] Check issue #022: Is the script message handler wired or still a stub?

### When you see Supabase queries:
- [ ] Check issue #012: Are you using `.select("*")` or explicit columns?

---

## Severity Levels

**MUST-PASS (Blocking):**
- No secrets in git
- No string interpolation in evaluateJavaScript()
- All Tasks stored and cancelled

**SHOULD-PASS (Strongly Suggested):**
- Formatters cached
- WKWebView sandbox enabled
- No catch-all switches on module enums

**NICE-TO-HAVE (Polish):**
- Explicit column selection
- Documentation updates
- Deprecation notices for replaced functions

---

## Related Documents

- Full guidance: `docs/INSTITUTIONAL_LEARNINGS_AND_PENDING_ITEMS.md`
- Security details: `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`
- PR #23 resolved P1/P2: feat/macos-swiftui-overhaul

---

## Common Issues Found in Recent Reviews

| Issue | Pattern | Fix |
|-------|---------|-----|
| Task leak | Fire-and-forget `Task { }` | Store as property, cancel before new |
| String injection | `"'\(symbol)'"` in JS | Use `JSONSerialization` |
| Credential exposure | Literal in Info.plist | Use `$(BUILD_VAR)` + Secrets.xcconfig |
| Formatter thrashing | `NumberFormatter()` in `body` | Create at file level |
| Duplicate endpoints | Two backtest functions | Keep one, deprecate other |
| Silent disconnect | `for await` exits, no retry | Implement reconnect with backoff |
| Wildcard selects | `.select("*")` everywhere | Use explicit column list |

---

*Last updated: 2026-03-01*
