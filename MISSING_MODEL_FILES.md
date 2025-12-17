# ⚠️ MISSING MODEL FILES - ADD THESE TO XCODE

## Problem
The build errors are because these **2 Model files** aren't in the Xcode project target yet:

1. ✅ `OptionsRankingResponse.swift` ← Defines `OptionRank`, `OptionSide`, `OptionsRankingsResponse`
2. ✅ `ScannerResponse.swift` ← Defines `ScannerAlert`, `ScannerWatchlistResponse`, `MLTrendLabel`

These files exist on disk but Xcode doesn't know about them!

## Quick Fix (Same as before, but for Models folder)

**In Xcode:**

1. **Right-click** on the `Models` folder in the Project Navigator (left sidebar)

2. Choose **"Add Files to SwiftBoltML..."**

3. Navigate to: `client-macos/SwiftBoltML/Models/`

4. **Select BOTH files**:
   - ☑️ `OptionsRankingResponse.swift`
   - ☑️ `ScannerResponse.swift`

5. In the dialog:
   - ⬜ **UNCHECK** "Copy items if needed"
   - ✅ **SELECT** "Create groups"
   - ✅ **CHECK** "SwiftBoltML" target

6. Click **"Add"**

7. **Clean Build Folder**: `Product → Clean Build Folder` (Cmd+Shift+K)

8. **Build**: `Product → Build` (Cmd+B)

## Why This Fixes Everything

Once these 2 model files are added, all the "Cannot find type" errors will disappear:

### From OptionsRankingResponse.swift:
- ✅ `OptionRank` → Used by OptionsRankerViewModel
- ✅ `OptionSide` → Used by OptionsRankerViewModel, APIClient
- ✅ `OptionsRankingsResponse` → Used by APIClient

### From ScannerResponse.swift:
- ✅ `ScannerAlert` → Used by AnalysisViewModel
- ✅ `ScannerWatchlistResponse` → Used by APIClient
- ✅ `MLTrendLabel` → Used by WatchlistItem (in ScannerResponse)

## Summary of All Files That Need to Be Added

If you haven't added them yet, here's the complete list:

### ViewModels/ (you may have already added these)
- ☑️ `OptionsRankerViewModel.swift`
- ☑️ `AnalysisViewModel.swift`

### Views/ (you may have already added these)
- ☑️ `OptionsRankerView.swift`
- ☑️ `AnalysisView.swift`

### Models/ (ADD THESE NOW!)
- ☑️ `OptionsRankingResponse.swift` ⚠️ **MISSING**
- ☑️ `ScannerResponse.swift` ⚠️ **MISSING**

## After Adding

Build output should show:
```
✅ Build Succeeded
```

Instead of:
```
❌ Cannot find type 'OptionSide' in scope
❌ Cannot find type 'ScannerAlert' in scope
etc.
```
