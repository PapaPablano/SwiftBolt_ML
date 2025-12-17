#!/bin/bash

echo "🔧 Attempting to add files to Xcode project..."

# Navigate to project directory
cd client-macos

# Use PlistBuddy to check if we can access the project
PROJECT_FILE="SwiftBoltML.xcodeproj/project.pbxproj"

if [ ! -f "$PROJECT_FILE" ]; then
    echo "❌ Project file not found!"
    exit 1
fi

echo "✅ Project file found"
echo ""
echo "📝 Manual steps required:"
echo ""
echo "In Xcode:"
echo "1. File → Add Files to 'SwiftBoltML'..."
echo "2. Navigate to SwiftBoltML/ViewModels/"
echo "3. Select: OptionsRankerViewModel.swift, AnalysisViewModel.swift"
echo "4. UNCHECK 'Copy items if needed'"
echo "5. SELECT 'Create groups'"
echo "6. CHECK 'SwiftBoltML' target"
echo "7. Click Add"
echo ""
echo "8. Repeat for SwiftBoltML/Views/"
echo "9. Select: OptionsRankerView.swift, AnalysisView.swift"
echo ""
echo "Then: Product → Clean Build Folder → Build"
echo ""
echo "See ADD_FILES_TO_XCODE.md for detailed instructions"

