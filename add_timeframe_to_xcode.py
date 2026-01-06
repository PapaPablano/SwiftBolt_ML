#!/usr/bin/env python3
"""Script to add Timeframe.swift to Xcode project."""

import re
import uuid
import sys

def generate_uuid():
    """Generate a unique ID for Xcode project file references."""
    return uuid.uuid4().hex[:24].upper()

def add_timeframe_to_xcode(project_path):
    """Add Timeframe.swift to the Xcode project."""
    
    # Read the project file
    with open(project_path, 'r') as f:
        content = f.read()
    
    # Create backup
    backup_path = project_path + '.backup2'
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"Created backup at: {backup_path}")
    
    # Generate unique IDs
    timeframe_build_id = f"TF{generate_uuid()}"
    timeframe_file_id = f"TF{generate_uuid()}"
    
    # Add to PBXBuildFile section
    pbx_build_pattern = r'(/\* Begin PBXBuildFile section \*/)'
    pbx_build_insert = f'''\\1
\t\t{timeframe_build_id} /* Timeframe.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {timeframe_file_id} /* Timeframe.swift */; }};'''
    
    content = re.sub(pbx_build_pattern, pbx_build_insert, content)
    
    # Add to PBXFileReference section
    pbx_file_pattern = r'(/\* Begin PBXFileReference section \*/)'
    pbx_file_insert = f'''\\1
\t\t{timeframe_file_id} /* Timeframe.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = Timeframe.swift; sourceTree = "<group>"; }};'''
    
    content = re.sub(pbx_file_pattern, pbx_file_insert, content)
    
    # Find Models group and add file reference
    # Look for the Models group children section
    models_pattern = r'(E7[A-F0-9]+ /\* Models \*/ = \{[^}]*children = \([^)]*)'
    match = re.search(models_pattern, content)
    if match:
        models_section = match.group(1)
        new_models = models_section + f'\n\t\t\t\t{timeframe_file_id} /* Timeframe.swift */,'
        content = content.replace(models_section, new_models)
        print("✓ Added to Models group")
    else:
        print("⚠ Could not find Models group")
    
    # Add to Sources build phase
    sources_pattern = r'(E7[A-F0-9]+ /\* Sources \*/ = \{[^}]*files = \([^)]*)'
    match = re.search(sources_pattern, content)
    if match:
        sources_section = match.group(1)
        new_sources = sources_section + f'\n\t\t\t\t{timeframe_build_id} /* Timeframe.swift in Sources */,'
        content = content.replace(sources_section, new_sources)
        print("✓ Added to Sources build phase")
    else:
        print("⚠ Could not find Sources build phase")
    
    # Write back
    with open(project_path, 'w') as f:
        f.write(content)
    
    print("✓ Successfully added Timeframe.swift to Xcode project!")

if __name__ == '__main__':
    project_path = 'client-macos/SwiftBoltML.xcodeproj/project.pbxproj'
    add_timeframe_to_xcode(project_path)
