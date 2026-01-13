#!/usr/bin/env python3
"""
Script to add WebChartControlsView.swift to Xcode project.
"""

import re
import uuid
import sys
import shutil


def generate_uuid():
    """Generate a unique ID for Xcode project file references."""
    return uuid.uuid4().hex[:24].upper()


def add_file_to_xcode_project(project_path):
    """Add WebChartControlsView.swift to the Xcode project."""

    # Read the project file
    with open(project_path, "r") as f:
        content = f.read()

    # Generate unique IDs
    build_id = f"WC{generate_uuid()}"
    file_id = f"WC{generate_uuid()}"

    # Find the PBXBuildFile section and add new entry
    pbx_build_pattern = r'(/\* Begin PBXBuildFile section \*/)'
    pbx_build_insert = (
        "\\1\n"
        f"\t\t{build_id} "
        "/* WebChartControlsView.swift in Sources */ = "
        f"{{isa = PBXBuildFile; fileRef = {file_id} "
        "/* WebChartControlsView.swift */; };"
    )

    content = re.sub(pbx_build_pattern, pbx_build_insert, content)

    # Find the PBXFileReference section and add new entry
    pbx_file_pattern = r'(/\* Begin PBXFileReference section \*/)'
    pbx_file_insert = (
        "\\1\n"
        f"\t\t{file_id} "
        "/* WebChartControlsView.swift */ = "
        "{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        "path = WebChartControlsView.swift; sourceTree = \"<group>\"; };"
    )

    content = re.sub(pbx_file_pattern, pbx_file_insert, content)

    # Add to Views group (find an existing view file and add after it)
    views_pattern = (
        r"(/\* Views \*/[^=]+=\s*{[^}]*children = \([^)]*)"
        r"(WebChartView\.swift[^;]*;)"
    )
    views_insert = (
        f"""\\1\\2
\t\t\t\t{file_id} /* WebChartControlsView.swift */,"""
    )

    content = re.sub(views_pattern, views_insert, content)

    # Add to PBXSourcesBuildPhase (compile sources)
    sources_pattern = (
        r"(/\* Sources \*/[^=]+=\s*{[^}]*files = \([^)]*)"
        r"(WebChartView\.swift in Sources[^;]*;)"
    )
    sources_insert = (
        f"""\\1\\2
\t\t\t\t{build_id} /* WebChartControlsView.swift in Sources */,"""
    )

    content = re.sub(sources_pattern, sources_insert, content)

    # Write the updated project file
    with open(project_path, "w") as f:
        f.write(content)

    print("✓ Successfully added WebChartControlsView.swift to Xcode project!")


if __name__ == "__main__":
    project_path = (
        "/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML.xcodeproj/"
        "project.pbxproj"
    )

    try:
        # Backup the original project file
        backup_path = f"{project_path}.backup2"
        shutil.copy2(project_path, backup_path)
        print(f"Created backup at: {backup_path}")

        add_file_to_xcode_project(project_path)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Restoring backup...", file=sys.stderr)
        try:
            shutil.copy2(backup_path, project_path)
            print("Backup restored successfully.", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
