#!/usr/bin/env python3
"""
Add WebChart files to Xcode project
Adds WebChartControlsView.swift, heikin-ashi.js, and tooltip-enhanced.js
"""

import os
import uuid
import re

PROJECT_FILE = "/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML.xcodeproj/project.pbxproj"

# Files to add with their details
FILES_TO_ADD = [
    {
        "path": "SwiftBoltML/Views/WebChartControlsView.swift",
        "name": "WebChartControlsView.swift",
        "type": "sourcecode.swift",
        "group": "Views"
    },
    {
        "path": "SwiftBoltML/Resources/WebChart/heikin-ashi.js",
        "name": "heikin-ashi.js",
        "type": "sourcecode.javascript",
        "group": "WebChart"
    },
    {
        "path": "SwiftBoltML/Resources/WebChart/tooltip-enhanced.js",
        "name": "tooltip-enhanced.js",
        "type": "sourcecode.javascript",
        "group": "WebChart"
    }
]

def generate_uuid():
    """Generate a UUID in Xcode format (24 hex chars)"""
    return uuid.uuid4().hex[:24].upper()

def add_files_to_xcode():
    """Add files to Xcode project"""
    
    # Read project file
    with open(PROJECT_FILE, 'r') as f:
        content = f.read()
    
    # Generate UUIDs for each file
    file_refs = []
    build_files = []
    
    for file_info in FILES_TO_ADD:
        file_ref_uuid = generate_uuid()
        build_file_uuid = generate_uuid()
        
        file_refs.append({
            "uuid": file_ref_uuid,
            "path": file_info["path"],
            "name": file_info["name"],
            "type": file_info["type"]
        })
        
        build_files.append({
            "uuid": build_file_uuid,
            "file_ref": file_ref_uuid
        })
    
    # Find the PBXFileReference section
    file_ref_section = re.search(r'/\* Begin PBXFileReference section \*/(.*?)/\* End PBXFileReference section \*/', content, re.DOTALL)
    if not file_ref_section:
        print("ERROR: Could not find PBXFileReference section")
        return False
    
    # Add file references
    new_file_refs = []
    for ref in file_refs:
        new_ref = f'\t\t{ref["uuid"]} /* {ref["name"]} */ = {{isa = PBXFileReference; lastKnownFileType = {ref["type"]}; path = {ref["name"]}; sourceTree = "<group>"; }};\n'
        new_file_refs.append(new_ref)
    
    # Insert before the end of PBXFileReference section
    insert_pos = file_ref_section.end() - len('/* End PBXFileReference section */')
    content = content[:insert_pos] + ''.join(new_file_refs) + content[insert_pos:]
    
    # Find the PBXBuildFile section
    build_file_section = re.search(r'/\* Begin PBXBuildFile section \*/(.*?)/\* End PBXBuildFile section \*/', content, re.DOTALL)
    if build_file_section:
        new_build_files = []
        for bf in build_files:
            # Only add build files for Swift files (not resources)
            if any(ref["uuid"] == bf["file_ref"] and ref["type"] == "sourcecode.swift" for ref in file_refs):
                ref_name = next(ref["name"] for ref in file_refs if ref["uuid"] == bf["file_ref"])
                new_bf = f'\t\t{bf["uuid"]} /* {ref_name} in Sources */ = {{isa = PBXBuildFile; fileRef = {bf["file_ref"]} /* {ref_name} */; }};\n'
                new_build_files.append(new_bf)
        
        if new_build_files:
            insert_pos = build_file_section.end() - len('/* End PBXBuildFile section */')
            content = content[:insert_pos] + ''.join(new_build_files) + content[insert_pos:]
    
    # Find Views group and add WebChartControlsView.swift
    views_group = re.search(r'([A-F0-9]{24}) /\* Views \*/ = \{[^}]*children = \([^)]*\);', content)
    if views_group:
        swift_ref = next((ref for ref in file_refs if ref["name"] == "WebChartControlsView.swift"), None)
        if swift_ref:
            # Add to children array
            children_match = re.search(r'(children = \([^)]*)', content[views_group.start():views_group.end()])
            if children_match:
                insert_text = f'\n\t\t\t\t{swift_ref["uuid"]} /* {swift_ref["name"]} */,'
                pos = views_group.start() + children_match.end()
                content = content[:pos] + insert_text + content[pos:]
    
    # Find WebChart group and add JS files
    webchart_group = re.search(r'([A-F0-9]{24}) /\* WebChart \*/ = \{[^}]*children = \([^)]*\);', content)
    if webchart_group:
        js_refs = [ref for ref in file_refs if ref["type"] == "sourcecode.javascript"]
        if js_refs:
            children_match = re.search(r'(children = \([^)]*)', content[webchart_group.start():webchart_group.end()])
            if children_match:
                insert_texts = [f'\n\t\t\t\t{ref["uuid"]} /* {ref["name"]} */,' for ref in js_refs]
                pos = webchart_group.start() + children_match.end()
                content = content[:pos] + ''.join(insert_texts) + content[pos:]
    
    # Find PBXSourcesBuildPhase and add Swift file
    sources_phase = re.search(r'([A-F0-9]{24}) /\* Sources \*/ = \{[^}]*files = \([^)]*\);', content)
    if sources_phase:
        swift_build = next((bf for bf in build_files if any(ref["uuid"] == bf["file_ref"] and ref["type"] == "sourcecode.swift" for ref in file_refs)), None)
        if swift_build:
            files_match = re.search(r'(files = \([^)]*)', content[sources_phase.start():sources_phase.end()])
            if files_match:
                ref_name = next(ref["name"] for ref in file_refs if ref["uuid"] == swift_build["file_ref"])
                insert_text = f'\n\t\t\t\t{swift_build["uuid"]} /* {ref_name} in Sources */,'
                pos = sources_phase.start() + files_match.end()
                content = content[:pos] + insert_text + content[pos:]
    
    # Write back
    with open(PROJECT_FILE, 'w') as f:
        f.write(content)
    
    print("✅ Successfully added files to Xcode project:")
    for file_info in FILES_TO_ADD:
        print(f"   - {file_info['name']}")
    
    return True

if __name__ == "__main__":
    print("Adding WebChart files to Xcode project...")
    if add_files_to_xcode():
        print("\n✅ Done! Rebuild your project in Xcode (Cmd+Shift+K, then Cmd+B)")
    else:
        print("\n❌ Failed to add files. Please add manually in Xcode.")
