# CI/CD Architecture

This document describes the refactored CI/CD pipeline that separates lightweight code quality checks from heavy ML validation.

## Overview

The previous monolithic `ci.yml` workflow installed 1GB+ of ML dependencies on every commit, even for simple code changes. The new architecture separates concerns:

```
┌─────────────────────────────────────┐
│  Every Push/PR to master/develop    │
└────────────────┬────────────────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌──────────────────┐   ┌──────────────────┐
│ ci-lightweight   │   │ ml-validation    │
│ (runs always)    │   │ (weekly/on-demand)
├──────────────────┤   ├──────────────────┤
│ ✅ ML Linting    │   │ ✅ Unit Tests    │
│ ✅ Edge Funcs    │   │ ✅ Coverage      │
│ ✅ Migrations    │   │ ✅ Security      │
│ ⏱️ ~5 min        │   │ ✅ Integration   │
└──────────────────┘   │ ⏱️ ~15-30 min    │
                       └──────────────────┘
```

## Workflows

### 1. `ci-lightweight.yml` - Fast Code Quality Checks
**Runs on**: Every push/PR to master/main/develop
**Duration**: ~5 minutes
**Purpose**: Gate code quality without heavy dependencies

#### Jobs:
- **detect-changes**: Uses `dorny/paths-filter` to determine what changed
- **lint-ml**: Runs linting tools only (NOT full ML stack)
  - Black (formatting)
  - isort (import sorting)
  - flake8 (linting)
  - mypy (type checking)
  - Bandit (security)
  - Safety (dependency scan)
- **test-edge-functions**: Deno-based edge function tests
- **validate-migrations**: SQL migration validation
- **ci-summary**: Generates summary report

#### Key Differences:
- ❌ Does NOT install pandas, numpy, scipy, sklearn, xgboost, lightgbm
- ✅ Only installs linting tools (~100MB)
- ✅ Uses GitHub Actions caching aggressively
- ✅ Can run in parallel safely

#### When to Use:
```bash
# On any code change to master/develop
git push origin feature-branch
# → ci-lightweight.yml runs automatically
```

---

### 2. `ml-validation.yml` - Comprehensive ML Testing
**Runs on**:
- Weekly schedule: Monday 2:00 UTC
- When `ml/requirements*.txt` changes
- Manual trigger via workflow_dispatch
- On PR/push to ml/requirements*.txt

**Duration**: ~15-30 minutes (2 Python versions in parallel)
**Purpose**: Full ML validation with coverage enforcement

#### Jobs:
- **test-ml** (Matrix: Python 3.10, 3.11)
  - Full unit test suite
  - Coverage reporting (target: ≥90%)
  - Diff coverage enforcement
  - Codecov integration
  - HTML coverage reports as artifacts
- **lint-ml-comprehensive**
  - Full ML dependencies installed
  - All linting tools
  - Security & vulnerability scanning
  - Bandit report artifact
- **integration-tests** (PR/push only, not on schedule)
  - ML pipeline component tests
  - End-to-end validation

#### When to Use:
```bash
# 1. On schedule (weekly)
#    → Runs automatically Monday 2:00 UTC

# 2. When changing dependencies
git add ml/requirements.txt
git commit -m "Update ML dependencies"
git push
# → ml-validation.yml runs automatically (both Python versions)

# 3. Manual trigger
# Go to GitHub Actions → ML Validation → Run workflow
# Optional: Select specific Python version(s)
```

---

### 3. `ml-orchestration.yml` - Nightly ML Pipeline
**Runs on**: Schedule or manual trigger (decoupled from Daily Data Refresh)
**Purpose**: Forecast generation, options processing, model health

**Status**: Unchanged - still runs nightly ML workloads
- ML forecasting (ensemble predictions)
- Options processing
- Model evaluation
- Data quality validation

---

### 4. Deprecated Workflows

#### `ci.yml` (DEPRECATED)
- **Status**: Kept for reference only
- **Trigger**: `workflow_dispatch` only
- **Action**: Shows deprecation warning and exits with error
- **Reason**: Split into ci-lightweight.yml + ml-validation.yml

#### `test-ml.yml` (DEPRECATED)
- **Status**: Kept for reference only
- **Trigger**: `workflow_dispatch` only
- **Action**: Shows deprecation warning and exits with error
- **Reason**: Replaced by ml-validation.yml (more comprehensive)

---

## Performance Improvements

### Before (Old ci.yml)
| Change Type | Jobs | Time | Dependencies |
|-------------|------|------|--------------|
| Fix typo in README | test-ml, lint-ml, test-edge-functions | 10+ min | pandas, numpy, scipy, sklearn, xgboost, lightgbm |
| Fix linting issue | test-ml, lint-ml, test-edge-functions | 10+ min | Full ML stack (1GB+) |
| Update Edge Function | test-ml, lint-ml, test-edge-functions | 10+ min | Full ML stack (unnecessary) |

### After (New Architecture)
| Change Type | Workflow | Time | Dependencies |
|-------------|----------|------|--------------|
| Fix typo in README | ci-lightweight | ~1 min | None (no code change) |
| Fix linting issue | ci-lightweight | ~2 min | Black, flake8, mypy, etc. (~100MB) |
| Update Edge Function | ci-lightweight | ~3 min | Deno only |
| Full ML test | ml-validation (on-demand) | ~15-30 min | Full ML stack |

**Benefit**: 70-90% faster CI for most code changes

---

## Environment Caching

Both workflows use aggressive caching:

```yaml
# ci-lightweight.yml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-lint-${{ hashFiles('.github/workflows/ci-lightweight.yml') }}
    restore-keys:
      - ${{ runner.os }}-pip-lint-

# ml-validation.yml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('ml/requirements*.txt') }}
    restore-keys:
      - ${{ runner.os }}-pip-${{ matrix.python-version }}-
```

Cache keys are based on:
- `requirements*.txt` hashes (ML validation only)
- Workflow file hash (ci-lightweight only)

This ensures cache invalidation only when dependencies actually change.

---

## Branch Protection Rules

### Recommended GitHub Settings

For maximum safety while allowing fast CI:

```
Branch: master

Require status checks to pass before merging:
  ✅ ci-lightweight / lint-ml
  ✅ ci-lightweight / test-edge-functions
  ✅ ci-lightweight / validate-migrations

  (Do NOT require ml-validation - it's on schedule/on-demand)

Require branches to be up to date before merging:
  ✅ Yes

Include administrators:
  ✅ Yes
```

### Why Not Require ml-validation?
- It only runs weekly + on-demand, not on every push
- Blocking PRs waiting for a weekly run would be frustrating
- The lightweight checks catch most issues
- ml-validation runs automatically when requirements.txt changes

---

## Migration Guide

If you have workflows that depend on the old ci.yml:

### ❌ DO NOT DO:
```yaml
# Don't reference deprecated workflows
on:
  workflow_run:
    workflows: ["CI - Comprehensive Tests"]  # ci.yml is now deprecated
```

### ✅ DO THIS:
```yaml
# Reference the lightweight workflow
on:
  workflow_run:
    workflows: ["CI - Lightweight (Code Quality)"]  # ci-lightweight.yml
```

### ❌ DO NOT DO:
```yaml
# Don't wait for ML tests in tight loops
if: needs.test-ml.result == 'success'
```

### ✅ DO THIS:
```yaml
# ML tests are on schedule, not on every push
if: needs.lint-ml.result == 'success'  # From ci-lightweight.yml
```

---

## Troubleshooting

### Q: My PR is waiting for ml-validation to pass
**A**: ml-validation only runs:
- Weekly (Monday 2:00 UTC)
- When requirements.txt changes
- On manual trigger

If you need to force a full ML test:
1. Go to GitHub Actions
2. Select "ML Validation - Comprehensive Tests"
3. Click "Run workflow"

### Q: Linting failed but I need to run full tests
**A**: Fix the linting issue first (it's fast):
```bash
cd ml
black src tests
isort src tests
```

Then push - ci-lightweight will pass, then ml-validation runs on schedule.

### Q: Why didn't my requirements.txt change trigger ml-validation?
**A**: Check the file path - it must be `ml/requirements*.txt`:
- ✅ `ml/requirements.txt`
- ✅ `ml/requirements-dev.txt`
- ❌ `requirements.txt` (wrong directory)

### Q: Why is ci.yml showing a deprecation warning?
**A**: ci.yml is deprecated. Use ci-lightweight.yml instead.

If you manually trigger ci.yml, it will fail immediately with a deprecation message. This is intentional to prevent accidental use.

---

## Next Steps

### To Use Immediately:
1. Update branch protection rules to require `ci-lightweight` jobs
2. Remove requirement for ml-validation (it's on schedule)
3. Update any workflows that reference old ci.yml

### To Monitor:
- Watch GitHub Actions for run times
- Verify coverage reports in Codecov
- Check weekly ml-validation runs

### To Optimize Further:
- Add `REDIS_FEATURE_CACHE` to ml-orchestration if Redis becomes available
- Consider splitting integration tests into separate on-demand workflow
- Add performance benchmarking to ml-validation

---

## Reference

### Files Modified
- ✨ `.github/workflows/ci-lightweight.yml` - NEW (lightweight code quality)
- ✨ `.github/workflows/ml-validation.yml` - NEW (comprehensive ML testing)
- 🔄 `.github/workflows/ci.yml` - DEPRECATED (kept for reference)
- 🔄 `.github/workflows/test-ml.yml` - DEPRECATED (kept for reference)
- → `.github/workflows/ml-orchestration.yml` - UNCHANGED
- → `.github/workflows/intraday-ingestion.yml` - UNCHANGED
- → `.github/workflows/daily-data-refresh.yml` - UNCHANGED

### Removed Requirements
- ❌ No longer need 1GB+ ML dependencies in ci.yml
- ❌ No longer duplicate testing in multiple workflows
- ❌ No longer block all PRs on heavy ML tests

### New Triggers
- ✅ Weekly ML validation (Monday 2:00 UTC)
- ✅ On-demand ML validation (manual trigger)
- ✅ Automatic on requirements.txt changes
- ✅ Aggressive pip caching by Python version
