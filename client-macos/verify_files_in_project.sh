#!/bin/bash

# Verify Files in Xcode Project
# Usage: ./verify_files_in_project.sh

cd "$(dirname "$0")"

echo "🔍 Checking which Swift files are missing from Xcode project..."
echo ""

MISSING_FILES=()
FOUND_FILES=()

FILES_TO_CHECK=(
    "SwiftBoltML/Models/SelectedContractState.swift"
    "SwiftBoltML/Views/ContractWorkbenchView.swift"
    "SwiftBoltML/Views/MultiHorizonForecastView.swift"
    "SwiftBoltML/Views/Workbench/WhyRankedTabView.swift"
    "SwiftBoltML/Views/Workbench/ContractTabView.swift"
    "SwiftBoltML/Views/Workbench/OverviewTabView.swift"
    "SwiftBoltML/Views/Workbench/KeyMetricsStrip.swift"
    "SwiftBoltML/Views/Workbench/ContractWorkbenchHeader.swift"
    "SwiftBoltML/Services/MarketDataService.swift"
)

for file in "${FILES_TO_CHECK[@]}"; do
    filename=$(basename "$file")
    if grep -q "$filename" SwiftBoltML.xcodeproj/project.pbxproj 2>/dev/null; then
        FOUND_FILES+=("$file")
        echo "✅ $filename - IN PROJECT"
    else
        MISSING_FILES+=("$file")
        echo "❌ $filename - MISSING FROM PROJECT"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo "🎉 SUCCESS! All files are in the Xcode project."
    echo ""
    echo "Next steps:"
    echo "1. Open Xcode: open SwiftBoltML.xcodeproj"
    echo "2. Build: ⌘+B"
    echo "3. Run: ⌘+R"
    echo ""
    exit 0
else
    echo "⚠️  ${#MISSING_FILES[@]} file(s) still missing from project:"
    echo ""
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    echo ""
    echo "📋 To fix:"
    echo "1. Open Xcode: open SwiftBoltML.xcodeproj"
    echo "2. For each missing file:"
    echo "   - Right-click the appropriate folder in Xcode"
    echo "   - Select 'Add Files to SwiftBoltML...'"
    echo "   - Navigate to the file"
    echo "   - Ensure 'Add to targets: SwiftBoltML' is CHECKED"
    echo "   - Click 'Add'"
    echo "3. Build: ⌘+B"
    echo ""
    echo "See BUILD_ERRORS_FIX.md for detailed instructions."
    echo ""
    exit 1
fi
