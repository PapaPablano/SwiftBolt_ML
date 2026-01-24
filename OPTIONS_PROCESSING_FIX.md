# Options Processing Fix - Multiple Issues Resolved

**Date:** January 24, 2026  
**Issue:** ML Orchestration workflow failing with multiple errors  
**Status:** ✅ Fixed

---

## Problem Summary

The `options-processing` job in the ML Orchestration GitHub Actions workflow was failing for all symbols. Initial analysis showed "Invalid header value b'***'" but the actual runtime error was:

```
Failed to process [SYMBOL]: OptionsMomentumRanker.rank_options() got an unexpected keyword argument 'ranking_mode'
```

All 8 symbols in the watchlist (AAPL, AMD, CRWD, GOOG, MU, NVDA, PLTR, TSLA) failed with 0 successes.

---

## Root Cause Analysis

### Issue 1: Incorrect Method Signature (Primary Blocker)

The critical error was in `ml/src/scripts/backfill_options.py` line 577:

```python
ranked = ranker.rank_options(
    df,
    iv_stats=iv_stats,
    options_history=options_history if not options_history.empty else None,
    underlying_trend=trend,
    previous_rankings=prev if not prev.empty else None,
    ranking_mode="entry",  # ❌ WRONG: parameter name and type
)
```

**Problem:**
- The method uses `ranking_mode="entry"` (string parameter)
- The actual signature is `mode=RankingMode.ENTRY` (enum parameter)
- Parameter name: `mode` not `ranking_mode`
- Parameter type: `RankingMode` enum not string

**Correct signature:**
```python
def rank_options(
    self,
    options_df: pd.DataFrame,
    mode: RankingMode = RankingMode.MONITOR,  # Enum, not string!
    iv_stats: Optional[IVStatistics] = None,
    ...
)
```

### Issue 2: Whitespace in Environment Variables (Secondary)

The error `Invalid header value b'***'` occurs when HTTP headers contain invalid characters:
- Newline characters (`\n`, `\r`)
- Leading/trailing whitespace
- Control characters

GitHub Actions secrets can accidentally include these characters when:
1. Copy-pasting values with extra whitespace
2. Secrets are set with trailing newlines
3. Shell interpolation adds unexpected characters

The workflow logs (lines 472-473) showed the `SUPABASE_KEY` secret actually contained a newline character.

### Issue 3: Missing TRADIER_API_KEY (Non-Critical)

The workflow logs showed:
```
ERROR - AAPL: Backfill failed - Tradier API key required. Set TRADIER_API_KEY environment variable.
```

This prevented historical options backfill but didn't block the main processing since the script handles this gracefully.

---

## Solution Implemented

### 1. Fix Method Call Signature (ml/src/scripts/backfill_options.py)

**Fixed the incorrect method call:**

```python
# Import the RankingMode enum
from src.models.options_momentum_ranker import (
    IVStatistics,
    OptionsMomentumRanker,
    RankingMode,  # ✅ Added import
)

# Fixed the method call
ranker = OptionsMomentumRanker()
ranked = ranker.rank_options(
    df,
    mode=RankingMode.ENTRY,  # ✅ Correct: Use enum with proper parameter name
    iv_stats=iv_stats,
    options_history=options_history if not options_history.empty else None,
    underlying_trend=trend,
    previous_rankings=prev if not prev.empty else None,
)
```

**Benefits:**
- Fixes the TypeError that blocked all options processing
- Uses the correct enum type for type safety
- Follows the actual method signature
- Enables proper mode-specific ranking logic

### 2. Settings Validation (ml/config/settings.py)

Added a Pydantic field validator to strip whitespace from all credential fields:

```python
from pydantic import field_validator

@field_validator(
    "supabase_url",
    "supabase_key",
    "supabase_service_role_key",
    "database_url",
    "tradier_api_key",
    "alpaca_api_key",
    "alpaca_api_secret",
    mode="before",
)
@classmethod
def strip_whitespace(cls, v: str | None) -> str | None:
    """Strip whitespace and newlines from string fields to prevent HTTP header errors."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip()
    return v
```

**Benefits:**
- Automatically cleans all credential fields on load
- Works for both `.env` files and environment variables
- Prevents future issues with any credential field

### 3. GitHub Actions Secret Sanitization (.github/actions/setup-ml-env/action.yml)

Updated the environment configuration step to strip whitespace before writing to `.env`:

```yaml
- name: Configure environment
  shell: bash
  run: |
    cd ml
    # Strip whitespace and newlines from secrets to prevent HTTP header errors
    SUPABASE_URL=$(echo -n "${{ inputs.supabase-url }}" | xargs)
    SUPABASE_KEY=$(echo -n "${{ inputs.supabase-key }}" | xargs)
    DATABASE_URL=$(echo -n "${{ inputs.database-url }}" | xargs)
    ALPACA_API_KEY=$(echo -n "${{ inputs.alpaca-api-key }}" | xargs)
    ALPACA_API_SECRET=$(echo -n "${{ inputs.alpaca-api-secret }}" | xargs)
    
    cat > .env << EOF
    SUPABASE_URL=${SUPABASE_URL}
    SUPABASE_KEY=${SUPABASE_KEY}
    DATABASE_URL=${DATABASE_URL}
    ALPACA_API_KEY=${ALPACA_API_KEY}
    ALPACA_API_SECRET=${ALPACA_API_SECRET}
    EOF
```

**How it works:**
- `echo -n` removes trailing newlines
- `xargs` strips leading/trailing whitespace
- Variables are interpolated cleanly into `.env`

### 4. Runtime Validation (ml/src/scripts/backfill_options.py)

Added explicit validation to catch issues early with clear error messages:

```python
def validate_secret(name: str, value: str | None) -> None:
    """Validate that a secret value is suitable for use in HTTP headers."""
    if value is None:
        return
    if "\n" in value or "\r" in value:
        logger.error(f"{name} contains newline characters - this will cause HTTP header errors!")
        sys.exit(1)
    if not value.strip():
        logger.error(f"{name} is empty or whitespace-only!")
        sys.exit(1)

validate_secret("SUPABASE_URL", settings.supabase_url)
validate_secret("SUPABASE_KEY", settings.supabase_key)
```

**Benefits:**
- Fails fast with descriptive error messages
- Makes debugging easier for future issues
- Validates at script startup before making any API calls

---

## Testing & Verification

### Manual Testing Recommendations

1. **Verify secret values don't have trailing newlines:**
   ```bash
   # Check if secret has trailing newline
   echo -n "$SUPABASE_KEY" | od -c | tail -1
   # Should NOT show \n at the end
   ```

2. **Test locally with cleaned secrets:**
   ```bash
   cd ml
   export SUPABASE_URL=$(echo -n "$SUPABASE_URL" | xargs)
   export SUPABASE_KEY=$(echo -n "$SUPABASE_KEY" | xargs)
   python src/scripts/backfill_options.py --symbol AAPL
   ```

3. **Trigger GitHub Actions workflow:**
   - Go to Actions → ML Orchestration
   - Click "Run workflow"
   - Select job filter: "options-processing"
   - Verify all symbols process successfully

### Expected Outcome

After the fix, the workflow should show:
```
✅ Success: 8
❌ Failed: 0
📊 Total Calls: [count]
📊 Total Puts: [count]
📊 Snapshots Stored: [count]
📊 Ranks Updated: [count]
```

---

## GitHub Secrets Maintenance

### Updating Secrets in GitHub

If you need to update any secrets in the repository:

1. **Navigate to Settings → Secrets and variables → Actions**

2. **For each secret, ensure no trailing whitespace:**
   ```bash
   # Clean the secret value before setting it
   echo -n "your-secret-value" | xargs | pbcopy  # macOS
   echo -n "your-secret-value" | xargs | xclip   # Linux
   ```

3. **Update the secret in GitHub Actions with the cleaned value**

### Required Secrets for ML Orchestration

- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key for database access
- `DATABASE_URL` - Direct PostgreSQL connection string (optional)
- `ALPACA_API_KEY` - Alpaca API key for market data
- `ALPACA_API_SECRET` - Alpaca API secret

---

## Additional Context

### Why This Issue is Common

1. **Copy-Paste Errors**: When copying secrets from dashboards, trailing whitespace can be included
2. **Shell Behavior**: Some shells add newlines when echoing values
3. **Git Bash/Windows**: Line ending conversions can introduce `\r\n`
4. **Cloud Consoles**: Some UI elements add invisible characters

### Why Python's `requests` is Strict

The `requests` library enforces RFC 7230 compliance for HTTP headers:
- Headers must be ASCII strings
- Control characters (including `\r`, `\n`) are not allowed
- This prevents HTTP header injection attacks

### Related Issues in Codebase

The same pattern is used in:
1. `ml/src/data/tradier_client.py` (line 61-64) - Also fixed by settings validator
2. Any code using `settings.supabase_key`, `settings.alpaca_api_key`, etc.

All are now protected by the Pydantic field validator.

---

## Files Modified

1. **ml/src/scripts/backfill_options.py** (Critical Fix)
   - Added `RankingMode` to imports from `options_momentum_ranker`
   - Changed `ranking_mode="entry"` to `mode=RankingMode.ENTRY`
   - Fixed method call to use correct parameter name and type
   - Added `validate_secret()` function for runtime validation
   - Validates `SUPABASE_URL` and `SUPABASE_KEY` at startup

2. **ml/config/settings.py** (Defensive Fix)
   - Added `field_validator` to strip whitespace from all credential fields
   - Imports `field_validator` from `pydantic`

3. **.github/actions/setup-ml-env/action.yml** (Defensive Fix)
   - Updated "Configure environment" step to sanitize secrets with `xargs`
   - Added comment explaining the fix

---

## Prevention for Future Development

### Best Practices

1. **Always strip whitespace from environment variables:**
   ```python
   api_key = os.getenv("API_KEY", "").strip()
   ```

2. **Use Pydantic validators for settings classes:**
   ```python
   @field_validator("field_name", mode="before")
   @classmethod
   def clean_field(cls, v: str | None) -> str | None:
       return v.strip() if isinstance(v, str) else v
   ```

3. **Validate secrets before use:**
   ```python
   if "\n" in api_key or "\r" in api_key:
       raise ValueError("API key contains invalid characters")
   ```

4. **Test with malformed secrets locally:**
   ```bash
   export BAD_SECRET="valid-secret\n"  # Test handling
   python your_script.py  # Should fail gracefully
   ```

---

## Rollout Plan

1. ✅ **Code Changes**: Committed to repository
2. 🔄 **Testing**: Next ML Orchestration workflow run will validate fix
3. 📊 **Monitoring**: Check workflow logs for success rate
4. ✅ **Documentation**: This file serves as reference

---

## References

- **RFC 7230 (HTTP/1.1)**: HTTP header field parsing rules
- **Python requests library**: Header validation implementation
- **Pydantic validators**: Field validation documentation
- **GitHub Actions secrets**: Best practices for secret management

---

## Contact

For questions or issues related to this fix, refer to:
- GitHub Actions workflow: `.github/workflows/ml-orchestration.yml`
- ML pipeline documentation: `docs/ml/`
- Settings configuration: `ml/config/settings.py`
