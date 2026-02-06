#!/usr/bin/env python3
"""
Check for Look-Ahead Bias in Features

Searches for common look-ahead bias patterns:
1. Using .shift(-N) (accessing future data)
2. Using future dates in calculations
3. Features that use target variable
4. Circular dependencies
"""

import sys
from pathlib import Path
import re

print("="*80)
print("LOOK-AHEAD BIAS CHECKER")
print("="*80)

# Files to check
files_to_check = [
    'src/features/temporal_indicators.py',
    'src/models/baseline_forecaster.py',
    'src/features/adaptive_thresholds.py',
]

print("\nChecking files for look-ahead bias patterns...\n")

issues_found = []

for file_path in files_to_check:
    full_path = Path(file_path)
    
    if not full_path.exists():
        print(f"⚠️  File not found: {file_path}")
        continue
    
    print(f"\nChecking: {file_path}")
    print("-" * 60)
    
    with open(full_path, 'r') as f:
        lines = f.readlines()
    
    file_issues = []
    
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        # Skip comments
        if line_stripped.startswith('#'):
            continue
        
        # Pattern 1: .shift(-N) - Negative shifts access future
        if re.search(r'\.shift\s*\(\s*-\s*\d+\s*\)', line):
            file_issues.append({
                'line': i,
                'code': line.strip(),
                'issue': 'CRITICAL: .shift(-N) accesses FUTURE data',
                'severity': '❌'
            })
        
        # Pattern 2: Accessing future rows with iloc
        if re.search(r'iloc\s*\[.*\+.*\]', line) and 'shift' not in line.lower():
            file_issues.append({
                'line': i,
                'code': line.strip(),
                'issue': 'WARNING: iloc[i+N] may access future',
                'severity': '⚠️ '
            })
        
        # Pattern 3: 'future' or 'forward' in variable names
        if re.search(r'\b(future|forward)_', line.lower()) and not line_stripped.startswith('#'):
            file_issues.append({
                'line': i,
                'code': line.strip(),
                'issue': 'WARNING: Variable name suggests future data',
                'severity': '⚠️ '
            })
        
        # Pattern 4: Rolling with negative window
        if re.search(r'\.rolling\s*\(.*-', line):
            file_issues.append({
                'line': i,
                'code': line.strip(),
                'issue': 'WARNING: Negative rolling window',
                'severity': '⚠️ '
            })
        
        # Pattern 5: pct_change with negative periods
        if re.search(r'pct_change\s*\(\s*periods\s*=\s*-', line):
            file_issues.append({
                'line': i,
                'code': line.strip(),
                'issue': 'CRITICAL: pct_change with negative periods',
                'severity': '❌'
            })
    
    if file_issues:
        for issue in file_issues:
            print(f"  {issue['severity']} Line {issue['line']}: {issue['issue']}")
            print(f"     Code: {issue['code'][:80]}..." if len(issue['code']) > 80 else f"     Code: {issue['code']}")
            print()
        issues_found.extend(file_issues)
    else:
        print("  ✓ No obvious look-ahead bias patterns found")

# Check for suspicious patterns in prepare_training_data
print("\n" + "="*80)
print("CHECKING prepare_training_data() LOGIC")
print("="*80)

baseline_path = Path('src/models/baseline_forecaster.py')
if baseline_path.exists():
    with open(baseline_path, 'r') as f:
        content = f.read()
    
    # Find prepare_training_data method
    method_match = re.search(
        r'def prepare_training_data\(.*?\):(.*?)(?=\n    def |\n\nclass |$)',
        content,
        re.DOTALL
    )
    
    if method_match:
        method_code = method_match.group(1)
        
        print("\nChecking label creation logic...\n")
        
        # Check if forward_returns uses shift correctly
        if 'forward_returns' in method_code:
            print("  Found forward_returns calculation")
            
            # Extract the line
            forward_lines = [line for line in method_code.split('\n') if 'forward_returns' in line and '=' in line]
            for line in forward_lines:
                print(f"    {line.strip()}")
            
            if '.shift(-' in method_code:
                print("\n  ✓ Using .shift(-N) to create forward returns (CORRECT)")
                print("    This shifts returns backward so we DON'T access future when indexing.")
            else:
                print("\n  ⚠️  Not using .shift(-N) - verify this is correct")
        
        # Check loop that creates training samples
        if 'for idx in range' in method_code:
            print("\n  Found training loop")
            
            # Check if we're accessing forward_returns at current idx
            if re.search(r'forward_returns\.iloc\[idx\]', method_code):
                print("  ✓ Accessing forward_returns.iloc[idx] (CORRECT)")
                print("    forward_returns was shifted, so iloc[idx] is safe.")
            elif re.search(r'forward_returns\.loc.*idx', method_code):
                print("  ✓ Accessing forward_returns via loc (CHECK: is index correct?)")
        
        # Check for assert_label_gap
        if 'assert_label_gap' in method_code:
            print("\n  ✓ Using assert_label_gap() to verify no look-ahead bias")
        else:
            print("\n  ⚠️  No assert_label_gap() found - consider adding")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

critical = [i for i in issues_found if i['severity'] == '❌']
warnings = [i for i in issues_found if i['severity'] == '⚠️ ']

print(f"\nTotal issues found: {len(issues_found)}")
print(f"  Critical (❌): {len(critical)}")
print(f"  Warnings (⚠️ ): {len(warnings)}")

if critical:
    print("\n❌ CRITICAL LOOK-AHEAD BIAS DETECTED!")
    print("\nThese issues MUST be fixed:")
    for issue in critical:
        print(f"  Line {issue['line']}: {issue['code'][:60]}...")
    print("\nIMPACT: Model is using future information, so validation accuracy is meaningless.")
    print("FIX: Remove .shift(-N) or negative indexing that accesses future data.")

elif warnings:
    print("\n⚠️  POTENTIAL ISSUES FOUND")
    print("\nReview these warnings:")
    for issue in warnings:
        print(f"  Line {issue['line']}: {issue['issue']}")
    print("\nRecommendation: Manually review each warning to confirm no look-ahead bias.")

else:
    print("\n✓ NO OBVIOUS LOOK-AHEAD BIAS PATTERNS FOUND")
    print("\nThis doesn't guarantee absence of look-ahead bias.")
    print("Manual review of feature engineering is still recommended.")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

if critical or warnings:
    print("\n1. Review flagged lines above")
    print("2. For each .shift(-N):")
    print("   - Verify it's for LABEL creation only (forward returns)")
    print("   - Ensure features DON'T use .shift(-N)")
    print("   - Check that shifted data is accessed at current idx, not future idx")
    
    print("\n3. For features, ONLY use:")
    print("   - .shift(+N) or .rolling() - looks backward")
    print("   - iloc[idx] where idx <= current - accesses past")
    print("   - NO .shift(-N), iloc[idx+N], or future references")

print("\n4. Test with assert_label_gap():")
print("   - Already integrated in baseline_forecaster.py")
print("   - Raises exception if features overlap with label window")

print("\n5. If 33% accuracy persists after fixing look-ahead bias:")
print("   - Features may not be predictive of future returns")
print("   - Consider different feature set or model architecture")

print("\n" + "="*80 + "\n")
