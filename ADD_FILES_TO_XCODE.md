# Adding New Phase 6 Files to Xcode Project

The build errors are because the new Swift files need to be added to the Xcode project target.

## Quick Fix (Easiest Method)

1. **In Xcode**, right-click on the `ViewModels` folder in the Project Navigator
2. Select **"Add Files to SwiftBoltML"**
3. Navigate to and select these files:
   - `OptionsRankerViewModel.swift`
   - `AnalysisViewModel.swift`

4. Right-click on the `Views` folder
5. Select **"Add Files to SwiftBoltML"**
6. Navigate to and select these files:
   - `OptionsRankerView.swift`
   - `AnalysisView.swift`

7. **Important**: In the dialog, make sure:
   - ✅ "Copy items if needed" is UNCHECKED (files are already in the right place)
   - ✅ "Create groups" is SELECTED
   - ✅ "SwiftBoltML" target is CHECKED

8. Click **"Add"**

9. Clean build folder: **Product → Clean Build Folder** (Cmd+Shift+K)

10. Build: **Product → Build** (Cmd+B)

## Files to Add

### ViewModels/
- [x] `OptionsRankerViewModel.swift` - Already created at: `client-macos/SwiftBoltML/ViewModels/OptionsRankerViewModel.swift`
- [x] `AnalysisViewModel.swift` - Already created at: `client-macos/SwiftBoltML/ViewModels/AnalysisViewModel.swift`

### Views/
- [x] `OptionsRankerView.swift` - Already created at: `client-macos/SwiftBoltML/Views/OptionsRankerView.swift`
- [x] `AnalysisView.swift` - Already created at: `client-macos/SwiftBoltML/Views/AnalysisView.swift`

## Alternative: Drag and Drop Method

1. Open **Finder** and navigate to:
   - `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/ViewModels/`
   - `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Views/`

2. In Xcode, make sure the Project Navigator is visible (Cmd+1)

3. **Drag** the new files from Finder into the appropriate folders in Xcode:
   - Drag `OptionsRankerViewModel.swift` and `AnalysisViewModel.swift` → ViewModels folder
   - Drag `OptionsRankerView.swift` and `AnalysisView.swift` → Views folder

4. In the dialog that appears:
   - ✅ UNCHECK "Copy items if needed"
   - ✅ SELECT "Create groups"
   - ✅ CHECK "SwiftBoltML" target

5. Click **"Finish"**

6. Clean and rebuild

## Verify Files Were Added

After adding the files, verify they're in the target:

1. Select any of the new files in Project Navigator
2. Open the File Inspector (Cmd+Option+1)
3. Under "Target Membership", ensure **SwiftBoltML** is checked

## Common Issues

### Issue: "Cannot find type 'OptionSide' in scope"
**Solution**: This means the files aren't in the build target. Follow the steps above.

### Issue: Files appear grayed out in Xcode
**Solution**: The file reference is broken. Delete the reference (select file, press Delete, choose "Remove Reference") and re-add the file.

### Issue: Duplicate symbol errors
**Solution**: The file was added twice. Select the file, check File Inspector, and ensure it's only in the target once.

## After Adding Files

Once the files are added, the build should succeed. The errors you saw:
```
Cannot find type 'OptionSide' in scope
Cannot find type 'OptionsRankingsResponse' in scope
Cannot find type 'ScannerWatchlistResponse' in scope
```

Will be resolved because:
- `OptionSide` is defined in `Models/OptionsRankingResponse.swift`
- `OptionsRankingsResponse` is defined in `Models/OptionsRankingResponse.swift`
- `ScannerWatchlistResponse` is defined in `Models/ScannerResponse.swift`
- `MLTrendLabel` is now defined in `Models/ScannerResponse.swift` (just added)

All these models are in the same module and will be accessible once the ViewModels and Views are in the build target.
