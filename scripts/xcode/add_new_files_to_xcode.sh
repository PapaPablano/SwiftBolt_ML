#!/bin/bash

# Script to add new Phase 6 Swift files to Xcode project
# This uses the ruby script approach that's already working in the project

PROJECT_DIR="/Users/ericpeterson/SwiftBolt_ML/client-macos"
PROJECT_FILE="$PROJECT_DIR/SwiftBoltML.xcodeproj"

echo "Adding new Swift files to Xcode project..."

# Create a Ruby script to add files
cat > /tmp/add_files.rb << 'RUBY_SCRIPT'
require 'xcodeproj'

project_path = ARGV[0]
project = Xcodeproj::Project.open(project_path)

# Get the main target
target = project.targets.first

# Files to add
files_to_add = [
  'SwiftBoltML/ViewModels/OptionsRankerViewModel.swift',
  'SwiftBoltML/ViewModels/AnalysisViewModel.swift',
  'SwiftBoltML/Views/OptionsRankerView.swift',
  'SwiftBoltML/Views/AnalysisView.swift'
]

files_to_add.each do |file_path|
  # Get the group path (e.g., "SwiftBoltML/ViewModels")
  group_path = File.dirname(file_path).split('/')

  # Navigate to the correct group
  group = project.main_group
  group_path.each do |path_component|
    group = group.groups.find { |g| g.display_name == path_component } ||
            group.new_group(path_component)
  end

  # Add file reference
  file_ref = group.new_file(File.basename(file_path))

  # Add to target
  target.add_file_references([file_ref])

  puts "Added: #{file_path}"
end

project.save
puts "Project saved successfully!"
RUBY_SCRIPT

# Run the Ruby script
ruby /tmp/add_files.rb "$PROJECT_FILE"

echo "Done! Files added to Xcode project."
echo "Please rebuild in Xcode."
