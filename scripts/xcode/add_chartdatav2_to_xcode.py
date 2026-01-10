#!/usr/bin/env python3
"""Add ChartDataV2Response.swift to Xcode project."""

import re
import uuid

# Read the project file
with open('client-macos/SwiftBoltML.xcodeproj/project.pbxproj', 'r') as f:
    content = f.read()

# Generate unique IDs
file_ref_id = 'CD' + uuid.uuid4().hex[:22].upper()
build_file_id = 'BD' + uuid.uuid4().hex[:22].upper()

# 1. Add PBXFileReference
file_ref = f'\t\t{file_ref_id} /* ChartDataV2Response.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = ChartDataV2Response.swift; sourceTree = "<group>"; }};'

# Find where to insert (after ChartResponse.swift)
chart_response_pattern = r'(A2000010233456780000010 /\* ChartResponse\.swift \*/ = \{isa = PBXFileReference;[^\}]+\};)'
content = re.sub(chart_response_pattern, r'\1\n' + file_ref, content)

# 2. Add PBXBuildFile
build_file = f'\t\t{build_file_id} /* ChartDataV2Response.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {file_ref_id} /* ChartDataV2Response.swift */; }};'

# Find where to insert (after ChartResponse.swift in Sources)
build_file_pattern = r'(A1000010233456780000010 /\* ChartResponse\.swift in Sources \*/ = \{isa = PBXBuildFile;[^\}]+\};)'
content = re.sub(build_file_pattern, r'\1\n' + build_file, content)

# 3. Add to Models group
models_group_pattern = r'(A2000010233456780000010 /\* ChartResponse\.swift \*/,)'
models_group_entry = f'\t\t\t\t{file_ref_id} /* ChartDataV2Response.swift */,'
content = re.sub(models_group_pattern, r'\1\n' + models_group_entry, content)

# 4. Add to Sources build phase
sources_phase_pattern = r'(A1000010233456780000010 /\* ChartResponse\.swift in Sources \*/,)'
sources_phase_entry = f'\t\t\t\t{build_file_id} /* ChartDataV2Response.swift in Sources */,'
content = re.sub(sources_phase_pattern, r'\1\n' + sources_phase_entry, content)

# Write back
with open('client-macos/SwiftBoltML.xcodeproj/project.pbxproj', 'w') as f:
    f.write(content)

print("✅ Successfully added ChartDataV2Response.swift to Xcode project")
print(f"   File Reference ID: {file_ref_id}")
print(f"   Build File ID: {build_file_id}")
