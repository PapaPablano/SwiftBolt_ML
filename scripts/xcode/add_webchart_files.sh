#!/bin/bash

# Script to add WebChart files to Xcode project
# This adds the new Swift and JavaScript files to the project

echo "Adding WebChart files to Xcode project..."

# Files to add
FILES=(
    "client-macos/SwiftBoltML/Views/WebChartControlsView.swift"
    "client-macos/SwiftBoltML/Resources/WebChart/heikin-ashi.js"
    "client-macos/SwiftBoltML/Resources/WebChart/tooltip-enhanced.js"
)

# Check if files exist
for file in "${FILES[@]}"; do
    if [ ! -f "/Users/ericpeterson/SwiftBolt_ML/$file" ]; then
        echo "ERROR: File not found: $file"
        exit 1
    fi
done

echo "All files found. Please add them manually in Xcode:"
echo ""
echo "1. In Xcode, right-click on 'Views' folder"
echo "   - Select 'Add Files to SwiftBoltML...'"
echo "   - Navigate to: client-macos/SwiftBoltML/Views/"
echo "   - Select: WebChartControlsView.swift"
echo "   - Check 'Copy items if needed'"
echo "   - Check 'SwiftBoltML' target"
echo "   - Click 'Add'"
echo ""
echo "2. In Xcode, right-click on 'Resources/WebChart' folder"
echo "   - Select 'Add Files to SwiftBoltML...'"
echo "   - Navigate to: client-macos/SwiftBoltML/Resources/WebChart/"
echo "   - Select: heikin-ashi.js and tooltip-enhanced.js"
echo "   - Check 'Copy items if needed'"
echo "   - Check 'SwiftBoltML' target"
echo "   - Click 'Add'"
echo ""
echo "Files to add:"
for file in "${FILES[@]}"; do
    echo "  ✓ $file"
done
