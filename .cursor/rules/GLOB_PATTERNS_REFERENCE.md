# Cursor Rules - Glob Patterns Reference

## Fixed Glob Patterns

The cursor rules have been updated to match your **actual project file structure**. Here's the mapping:

---

## File Locations and Patterns

### 1. Python Backend Rules
**Rule File**: `python-fastapi-backend.mdc`  
**Glob Patterns**:
```
ml/**/*.py
ml/src/**/*.py
ml/api/**/*.py
```

**Actual Directories**:
- `ml/src/` - Main source code
- `ml/api/` - API endpoints
- `ml/scripts/` - Utility scripts
- `ml/tests/` - Test files

**Example Files Matched**:
- `ml/src/models/forecast.py`
- `ml/api/routes/options.py`
- `ml/src/utils/validators.py`

---

### 2. ML Pipeline Rules
**Rule File**: `ml-pipeline-standards.mdc`  
**Glob Patterns**:
```
ml/src/**/*.py
ml/api/**/*.py
ml/tests/**/*.py
```

**Actual Directories**:
- `ml/src/` - ML models and data processing
- `ml/tests/` - Test suite for models
- `ml/api/` - API that uses ML models

**Example Files Matched**:
- `ml/src/models/walk_forward.py`
- `ml/src/features/engineering.py`
- `ml/tests/test_backtest.py`

---

### 3. Options & Greeks Rules
**Rule File**: `options-greeks-trading.mdc`  
**Glob Patterns**:
```
ml/src/**/*.py
ml/api/**/*.py
```

**Actual Directories**:
- `ml/src/` - Greeks calculation and options pricing
- `ml/api/` - API endpoints for options data

**Example Files Matched**:
- `ml/src/trading/greeks.py`
- `ml/src/trading/options.py`
- `ml/api/routes/options_chain.py`

---

### 4. Swift Rules
**Rule File**: `swift-real-time-charting.mdc`  
**Glob Patterns**:
```
client-macos/**/*.swift
client-macos/SwiftBoltML/**/*.swift
```

**Actual Directories**:
- `client-macos/SwiftBoltML/` - Main Swift app source
- `client-macos/SwiftBoltML.xcodeproj/` - Xcode project

**Example Files Matched**:
- `client-macos/SwiftBoltML/Views/ChartView.swift`
- `client-macos/SwiftBoltML/Models/PortfolioModel.swift`
- `client-macos/SwiftBoltML/Services/APIClient.swift`

---

## Project Structure Reference

```
SwiftBolt_ML/
├── .cursor/
│   └── rules/
│       ├── .cursorrules                    ← Master config
│       ├── python-fastapi-backend.mdc      ← ml/**/*.py
│       ├── ml-pipeline-standards.mdc       ← ml/src/**/*.py, ml/tests/**/*.py
│       ├── options-greeks-trading.mdc      ← ml/src/**/*.py, ml/api/**/*.py
│       ├── swift-real-time-charting.mdc    ← client-macos/**/*.swift
│       └── README.md
│
├── ml/                                     ← Python backend & ML
│   ├── src/                                ← Source code
│   │   ├── models/
│   │   ├── features/
│   │   ├── trading/
│   │   ├── data/
│   │   └── utils/
│   ├── api/                                ← FastAPI routes
│   │   └── routes/
│   ├── tests/                              ← Test suite
│   ├── scripts/                            ← Utility scripts
│   └── requirements.txt
│
├── client-macos/                           ← Swift app
│   ├── SwiftBoltML/                        ← App source
│   │   ├── Views/
│   │   ├── Models/
│   │   ├── Services/
│   │   ├── Utils/
│   │   └── App.swift
│   └── SwiftBoltML.xcodeproj/
│
├── backend/                                ← Database & deployment
│   ├── lib/
│   ├── scripts/
│   ├── supabase/
│   └── github_actions/
│
└── (documentation, examples, etc.)
```

---

## How Glob Patterns Work in Cursor

### Pattern Syntax
- `*` - Matches any characters except `/`
- `**` - Matches any number of directories
- `*.py` - Matches all Python files
- `**/*.py` - Matches Python files in any subdirectory

### Examples

**Pattern**: `ml/**/*.py`  
**Matches**:
- ✅ `ml/src/models/forecast.py`
- ✅ `ml/api/routes/options.py`
- ✅ `ml/src/trading/greeks.py`
- ❌ `backend/lib/handler.js` (wrong directory)
- ❌ `client-macos/SwiftBoltML/App.swift` (wrong extension)

**Pattern**: `client-macos/**/*.swift`  
**Matches**:
- ✅ `client-macos/SwiftBoltML/Views/ChartView.swift`
- ✅ `client-macos/SwiftBoltML/Models/PortfolioModel.swift`
- ❌ `ml/src/models/forecast.py` (wrong directory)
- ❌ `client-macos/build/artifacts.txt` (wrong extension)

---

## Verification

To verify that patterns work correctly in Cursor IDE:

1. **Open a file** in one of the matched directories
   - Example: `ml/src/models/forecast.py`

2. **Check Cursor's context** - Should show:
   - Applicable `.mdc` rules
   - Master `.cursorrules` context

3. **Look for rule indicators** in Cursor IDE:
   - Rules applied based on file type and location
   - Code suggestions follow your patterns

---

## Common Issues and Solutions

### Issue: "Glob pattern doesn't match any files"

**Cause**: Pattern points to non-existent directory  
**Solution**: Check actual directory structure and update pattern

**Example Fix**:
```
❌ Wrong: backend/trading/**/*.py  (directory doesn't exist)
✅ Fixed: ml/src/**/*.py          (correct directory)
```

### Issue: Rules not applying to specific file

**Cause**: File path doesn't match glob pattern  
**Solution**: Verify file location matches one of the patterns

**Example**:
```
File: ml/src/trading/greeks.py
Rules: options-greeks-trading.mdc
Patterns: ml/src/**/*.py, ml/api/**/*.py
✅ Matches: ml/src/**/*.py → greeks.py included
```

---

## Adding New Rules in the Future

When creating new `.mdc` files:

1. **Check the actual directory** where files live:
   ```bash
   ls -la ml/src/trading/  # See what's actually there
   ```

2. **Build glob patterns** to match those directories:
   ```yaml
   globs: ml/src/trading/**/*.py, ml/api/**/*.py
   ```

3. **Test the pattern** against real files:
   - ✅ Does it match files you want?
   - ❌ Does it exclude files you don't want?

4. **Update in rule file header**:
   ```yaml
   ---
   description: Your rule description
   globs: ml/src/**/*.py, ml/api/**/*.py
   ---
   ```

---

## Summary Table

| Rule File | Glob Patterns | Directory | File Types |
|-----------|---------------|-----------|------------|
| python-fastapi-backend.mdc | `ml/**/*.py` | ml/ | Python |
| ml-pipeline-standards.mdc | `ml/src/**/*.py`, `ml/tests/**/*.py` | ml/src/, ml/tests/ | Python |
| options-greeks-trading.mdc | `ml/src/**/*.py`, `ml/api/**/*.py` | ml/src/, ml/api/ | Python |
| swift-real-time-charting.mdc | `client-macos/**/*.swift` | client-macos/ | Swift |

---

**Updated**: January 23, 2026  
**Status**: ✅ All glob patterns verified and corrected to match actual project structure
