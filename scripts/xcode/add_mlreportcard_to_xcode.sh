#!/bin/bash

# Script to add MLReportCard.swift to the Xcode project
# This opens Xcode with the file selected so you can easily add it

echo "Opening Xcode project..."
open -a Xcode /Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML.xcodeproj

echo ""
echo "==========================================="
echo "ACTION REQUIRED IN XCODE:"
echo "==========================================="
echo ""
echo "1. In Xcode, right-click on the 'Views' folder"
echo "2. Select 'Add Files to SwiftBoltML...'"
echo "3. Navigate to: client-macos/SwiftBoltML/Views/"
echo "4. Select: MLReportCard.swift"
echo "5. UNCHECK 'Copy items if needed'"
echo "6. CHECK 'SwiftBoltML' target"
echo "7. Click 'Add'"
echo ""
echo "Then build the project (Cmd+B)"
echo ""
echo "==========================================="
echo ""

# Also reveal the file in Finder to make it easy to find
open -R /Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Views/MLReportCard.swift
