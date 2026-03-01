---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, security, credentials, git-history]
dependencies: []
---

# 001: Supabase anon key and project URL hardcoded in git history

## Problem Statement

The Supabase anon key and project URL are committed in plaintext to `Info.plist`, which is tracked by git. The key (`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`) encodes `role: anon`, project ref `cygflaemtmwiwaviclks`, and does not expire until 2080. Anyone with read access to this repository (including forks, CI logs, or git history) can extract a valid credential. **BLOCKS MERGE.**

## Findings

**File:** `client-macos/SwiftBoltML/Info.plist` lines 34-37

```xml
<key>SUPABASE_URL</key>
<string>https://cygflaemtmwiwaviclks.supabase.co</string>
<key>SUPABASE_ANON_KEY</key>
<string>eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...</string>
```

- Key present since commit `2a9e558`, still in HEAD commit on this PR
- `Info.plist` is tracked by git (confirmed via `git ls-files`), not listed in `.gitignore`
- The anon key can: execute queries against tables with absent/misconfigured RLS, invoke Edge Functions with `verify_jwt: false`, enumerate public resources
- The same value is bundled in release `.app` binaries (trivially extractable with `plutil`)

**Source:** security-sentinel agent

## Proposed Solutions

### Option A: Xcode Build Variables (Recommended)
- Replace `<string>` values with `$(SUPABASE_URL)` and `$(SUPABASE_ANON_KEY)` Xcode build variable references
- Inject values from a `.xcconfig` file that is gitignored
- Rotate the compromised key immediately in Supabase dashboard (Settings → API → Regenerate anon key)
- Purge key from git history using BFG Repo-Cleaner or `git filter-repo`
- **Pros:** Eliminates credential from source control; standard Xcode pattern
- **Cons:** Requires CI/CD secret injection; small setup overhead
- **Effort:** Medium | **Risk:** Low (existing `Config.swift` already reads from env/plist)

### Option B: Gitignore + .env.local only (Stop-gap)
- Add `**/Info.plist` to `.gitignore`
- Still requires rotating the compromised key and purging history
- **Pros:** Fast to implement
- **Cons:** Breaks normal Xcode workflow; other non-sensitive plist keys become untracked
- **Effort:** Small | **Risk:** Medium (easy to accidentally commit again)

### Option C: Keychain-only at runtime (Long-term)
- Remove credentials from Info.plist entirely
- On first launch, display setup UI prompting user to enter their Supabase URL/key, store in macOS Keychain
- `Config.swift` already supports Keychain reads
- **Pros:** Most secure; credentials never in any file
- **Cons:** Requires first-run UX; breaks automated testing
- **Effort:** Large | **Risk:** Low

## Recommended Action

Option A (Xcode build variables) combined with immediate key rotation and git history purge.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Info.plist`
- `client-macos/SwiftBoltML/Services/Config.swift` (already has Keychain/env fallback)

**Key to rotate:** Any Supabase anon key starting with `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9` in this repo

## Acceptance Criteria

- [ ] Supabase anon key rotated in Supabase dashboard
- [ ] `Info.plist` no longer contains the key value (uses build variable reference)
- [ ] `.xcconfig` or equivalent is listed in `.gitignore`
- [ ] Git history purged of compromised key value
- [ ] App still builds and connects to Supabase after change
- [ ] CI/CD pipeline injects the new key value at build time

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- [Xcode Build Configuration Files (.xcconfig)](https://developer.apple.com/documentation/xcode/adding-a-build-configuration-file)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
