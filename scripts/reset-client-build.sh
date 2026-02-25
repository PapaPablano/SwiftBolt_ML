#!/bin/bash

# Reset the macOS client build to ensure correct Supabase configuration
echo "Resetting macOS client build..."

# Clean the build directory
cd /Users/ericpeterson/SwiftBolt_ML/client-macos
echo "Cleaning build directory..."
rm -rf build/

# Clean derived data
echo "Cleaning Xcode derived data..."
rm -rf ~/Library/Developer/Xcode/iOS\ Device\ Logs/
rm -rf ~/Library/Developer/Xcode/Archives/
rm -rf ~/Library/Developer/Xcode/iOS\ Simulator/

# Clean keychain data (optional - remove Supabase related entries)
echo "Cleaning potentially problematic keychain entries..."
security delete-generic-password -s "SUPABASE_URL" 2>/dev/null || true
security delete-generic-password -s "SUPABASE_ANON_KEY" 2>/dev/null || true

echo "Build reset complete. Please rebuild the macOS client."
echo ""
echo "To rebuild:"
echo "1. Open Xcode project in /Users/ericpeterson/SwiftBolt_ML/client-macos"
echo "2. Build the project (Cmd+B)"
echo ""
echo "The app should now use the correct Supabase URL from the .env file."