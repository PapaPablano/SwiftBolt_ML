---
status: resolved
priority: p2
issue_id: "074"
tags: [code-review, security, auth, swift]
dependencies: []
---

# Raw auth error messages exposed to UI — account enumeration risk

## Problem Statement

`AuthController` exposes `error.localizedDescription` directly in the UI for all auth failures. Supabase Auth returns distinct messages for different failure modes ("Invalid login credentials", "User already registered"), enabling account enumeration — an attacker can determine whether an email address has an account.

## Findings

**File:** `client-macos/SwiftBoltML/ViewModels/AuthController.swift`

```swift
// Line 64-67 (signIn)
} catch {
    errorMessage = error.localizedDescription   // ← exposes Supabase internals
    Self.logger.error("Sign in failed: \(error)")
}

// Line 89-92 (signUp) — same pattern
// Line 100-103 (signOut) — same pattern
```

Also: `LoginView.swift` only validates non-empty fields with no minimum password length:
```swift
guard !email.isEmpty, !password.isEmpty else { return }
```

## Proposed Solutions

### Option A: Generic user-facing messages (Recommended)

Map all auth errors to generic messages while preserving full error in logs:

```swift
} catch {
    Self.logger.error("Sign in failed: \(error)")
    errorMessage = "Unable to sign in. Please check your credentials and try again."
}
```

For sign-up:
```swift
} catch {
    Self.logger.error("Sign up failed: \(error)")
    errorMessage = "Unable to create account. Please try again."
}
```

**Pros:** Prevents account enumeration, standard security practice. **Cons:** Less actionable for the user.

### Option B: Error type mapping with limited messages

Parse `AuthError` types and return specific but safe messages:

```swift
} catch let error as AuthError {
    switch error {
    case .sessionNotFound:
        errorMessage = "Session expired. Please sign in again."
    default:
        errorMessage = "Authentication failed. Please try again."
    }
}
```

**Pros:** Better UX than Option A. **Cons:** More code, error type API may change.

### Option C: Add minimum password length validation

Complementary to Options A/B — add in `LoginView.submit()`:

```swift
if isSignUp && password.count < 8 {
    errorMessage = "Password must be at least 8 characters"
    return
}
```

## Acceptance Criteria

- [ ] Auth error messages don't distinguish "user not found" from "wrong password"
- [ ] Detailed error is logged via `os.log` for debugging
- [ ] Password length validated client-side on sign-up (8+ chars)
- [ ] UI shows friendly, non-revealing error message

## Work Log

- 2026-03-02: Identified during PR #25 review by Security Sentinel

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/ViewModels/AuthController.swift` lines 64, 89, 100
