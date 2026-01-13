#!/usr/bin/env python3
"""
Script to add new Swift files to Xcode project.
Adds OptionContract.swift, OptionsChainResponse.swift,
OptionsChainViewModel.swift, and OptionsChainView.swift
"""

import re
import uuid
import sys


def generate_uuid():
    """Generate a unique ID for Xcode project file references."""
    return uuid.uuid4().hex[:24].upper()


def add_files_to_xcode_project(project_path):
    """Add the new Swift files to the Xcode project."""

    # Read the project file
    with open(project_path, 'r') as f:
        content = f.read()

    # Generate unique IDs for each file (2 IDs per file: PBXBuildFile and
    # PBXFileReference)
    option_contract_build_id = f"A1{generate_uuid()}"
    option_contract_file_id = f"A2{generate_uuid()}"

    options_response_build_id = f"A1{generate_uuid()}"
    options_response_file_id = f"A2{generate_uuid()}"

    options_vm_build_id = f"A1{generate_uuid()}"
    options_vm_file_id = f"A2{generate_uuid()}"

    options_view_build_id = f"A1{generate_uuid()}"
    options_view_file_id = f"A2{generate_uuid()}"

    # Find the PBXBuildFile section and add new entries
    pbx_build_pattern = r'(/\* Begin PBXBuildFile section \*/)'
    pbx_build_insert = (
        "\\1\n"
        f"\t\t{option_contract_build_id} "
        "/* OptionContract.swift in Sources */ = "
        "{isa = PBXBuildFile; fileRef = "
        f"{option_contract_file_id} /* OptionContract.swift */; }};\n"
        f"\t\t{options_response_build_id} "
        "/* OptionsChainResponse.swift in Sources */ = "
        "{isa = PBXBuildFile; fileRef = "
        f"{options_response_file_id} /* OptionsChainResponse.swift */; }};\n"
        f"\t\t{options_vm_build_id} "
        "/* OptionsChainViewModel.swift in Sources */ = "
        "{isa = PBXBuildFile; fileRef = "
        f"{options_vm_file_id} /* OptionsChainViewModel.swift */; }};\n"
        f"\t\t{options_view_build_id} "
        "/* OptionsChainView.swift in Sources */ = "
        "{isa = PBXBuildFile; fileRef = "
        f"{options_view_file_id} /* OptionsChainView.swift */; }};"
    )

    content = re.sub(
        pbx_build_pattern,
        pbx_build_insert,
        content,
    )

    # Find the PBXFileReference section and add new entries
    pbx_file_pattern = r'(/\* Begin PBXFileReference section \*/)'
    pbx_file_insert = (
        "\\1\n"
        f"\t\t{option_contract_file_id} /* OptionContract.swift */ = "
        "{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        "path = OptionContract.swift; sourceTree = \"<group>\"; }};\n"
        f"\t\t{options_response_file_id} /* OptionsChainResponse.swift */ = "
        "{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        "path = OptionsChainResponse.swift; sourceTree = \"<group>\"; }};\n"
        f"\t\t{options_vm_file_id} /* OptionsChainViewModel.swift */ = "
        "{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        "path = OptionsChainViewModel.swift; sourceTree = \"<group>\"; }};\n"
        f"\t\t{options_view_file_id} /* OptionsChainView.swift */ = "
        "{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        "path = OptionsChainView.swift; sourceTree = \"<group>\"; }};"
    )

    content = re.sub(
        pbx_file_pattern,
        pbx_file_insert,
        content,
    )

    # Add to Models group (find Models group and add files)
    models_pattern = (
        r'(/\* Models \*/[^=]+=\s*{[^}]*children = \([^)]*)'
        r'(NewsItem\.swift[^;]*;)'
    )
    models_insert = f'''\\1\\2
\t\t\t\t{option_contract_file_id} /* OptionContract.swift */,
\t\t\t\t{options_response_file_id} /* OptionsChainResponse.swift */,'''

    content = re.sub(
        models_pattern,
        models_insert,
        content,
    )

    # Add to ViewModels group
    viewmodels_pattern = (
        r'(/\* ViewModels \*/[^=]+=\s*{[^}]*children = \([^)]*)'
        r'(NewsViewModel\.swift[^;]*;)'
    )
    viewmodels_insert = f'''\\1\\2
\t\t\t\t{options_vm_file_id} /* OptionsChainViewModel.swift */,'''

    content = re.sub(
        viewmodels_pattern,
        viewmodels_insert,
        content,
    )

    # Add to Views group
    views_pattern = (
        r'(/\* Views \*/[^=]+=\s*{[^}]*children = \([^)]*)'
        r'(NewsListView\.swift[^;]*;)'
    )
    views_insert = f'''\\1\\2
\t\t\t\t{options_view_file_id} /* OptionsChainView.swift */,'''

    content = re.sub(
        views_pattern,
        views_insert,
        content,
    )

    # Add to PBXSourcesBuildPhase (compile sources)
    sources_pattern = (
        r'(/\* Sources \*/[^=]+=\s*{[^}]*files = \([^)]*)'
        r'(NewsItem\.swift in Sources[^;]*;)'
    )
    sources_insert = (
        "\\1\\2\n"
        f"\t\t\t\t{option_contract_build_id} "
        "/* OptionContract.swift in Sources */,\n"
        f"\t\t\t\t{options_response_build_id} "
        "/* OptionsChainResponse.swift in Sources */,\n"
        f"\t\t\t\t{options_vm_build_id} "
        "/* OptionsChainViewModel.swift in Sources */,\n"
        f"\t\t\t\t{options_view_build_id} "
        "/* OptionsChainView.swift in Sources */,"
    )

    content = re.sub(
        sources_pattern,
        sources_insert,
        content,
    )

    # Write the updated project file
    with open(project_path, 'w') as f:
        f.write(content)

    print("✓ Successfully added files to Xcode project!")
    print("  - OptionContract.swift")
    print("  - OptionsChainResponse.swift")
    print("  - OptionsChainViewModel.swift")
    print("  - OptionsChainView.swift")
    print("\nYou can now build the project in Xcode.")


if __name__ == "__main__":
    project_path = (
        "/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML.xcodeproj/"
        "project.pbxproj"
    )

    try:
        # Backup the original project file
        import shutil
        backup_path = f"{project_path}.backup"
        shutil.copy2(project_path, backup_path)
        print(f"Created backup at: {backup_path}")

        add_files_to_xcode_project(project_path)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Restoring backup...", file=sys.stderr)
        try:
            shutil.copy2(backup_path, project_path)
            print("Backup restored successfully.", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
