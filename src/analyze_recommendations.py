#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze recommendations.json for potential issues"""

import json
from pathlib import Path
from typing import Dict, List, Optional


def analyze_recommendations(json_file: Optional[Path] = None, verbose: bool = True) -> Dict[str, List]:
    """Analyze recommendations.json for potential issues.
    
    Args:
        json_file: Path to recommendations.json file. If None, uses default location.
        verbose: If True, print findings to stdout.
    
    Returns:
        Dictionary with issue categories as keys and lists of problematic entries as values.
    """
    if json_file is None:
        # Default to web/recommendations.json relative to project root
        project_root = Path(__file__).parent.parent
        json_file = project_root / 'web' / 'recommendations.json'
    
    if not json_file.exists():
        if verbose:
            print(f"Error: {json_file} not found")
        return {}
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check for issues
    issues = {
        'unknown_names': [],
        'very_short_names': [],
        'names_with_newlines': [],
        'no_phone': [],
        'no_service': [],
        'no_date': [],
        'invalid_phones': []
    }
    
    for rec in data:
        name = rec.get('name', '')
        phone = rec.get('phone', '')
        service = rec.get('service')
        date = rec.get('date')
        
        # Unknown names
        if name == 'Unknown':
            issues['unknown_names'].append(rec)
        
        # Very short names (<= 2 chars)
        if len(name) <= 2:
            issues['very_short_names'].append(rec)
        
        # Personal contacts that shouldn't be recommendations
        if name == 'אבא':  # 'אבא' (dad) - not a recommendation
            issues['very_short_names'].append(rec)
        
        # Names with newlines
        if '\n' in name:
            issues['names_with_newlines'].append(rec)
        
        # Missing data
        if not phone:
            issues['no_phone'].append(rec)
        if not service:
            issues['no_service'].append(rec)
        if not date:
            issues['no_date'].append(rec)
        
        # Invalid phone numbers (too short or suspicious)
        if phone and len(phone.replace('+', '').replace('-', '').replace(' ', '')) < 7:
            issues['invalid_phones'].append(rec)
    
    if verbose:
        _print_analysis_results(data, issues)
    
    return issues


def _print_analysis_results(data: List[Dict], issues: Dict[str, List]):
    """Print analysis results to stdout."""
    import sys
    
    print(f"Total recommendations: {len(data)}\n")
    sys.stdout.flush()
    
    # Check if there are any real issues (excluding informational ones)
    has_real_issues = any(issues[k] for k in ['unknown_names', 'very_short_names', 'names_with_newlines', 'no_phone', 'invalid_phones'])
    
    if has_real_issues:
        print("=== ISSUES FOUND ===\n")
        sys.stdout.flush()
    
    if issues['unknown_names']:
        print(f"❌ Unknown names: {len(issues['unknown_names'])}")
        for rec in issues['unknown_names'][:5]:
            print(f"   - Phone: {rec.get('phone')}, Service: {rec.get('service')}")
        if len(issues['unknown_names']) > 5:
            print(f"   ... and {len(issues['unknown_names']) - 5} more")
        print()
        sys.stdout.flush()
    
    if issues['very_short_names']:
        print(f"⚠️  Very short names (<=2 chars): {len(issues['very_short_names'])}")
        for rec in issues['very_short_names'][:10]:
            print(f"   - \"{rec.get('name')}\" (phone: {rec.get('phone')})")
        if len(issues['very_short_names']) > 10:
            print(f"   ... and {len(issues['very_short_names']) - 10} more")
        print()
        sys.stdout.flush()
    
    if issues['names_with_newlines']:
        print(f"⚠️  Names with newlines: {len(issues['names_with_newlines'])}")
        for rec in issues['names_with_newlines']:
            print(f"   - \"{rec.get('name')}\" (phone: {rec.get('phone')})")
        print()
        sys.stdout.flush()
    
    if issues['no_phone']:
        print(f"❌ No phone: {len(issues['no_phone'])}")
        print()
        sys.stdout.flush()
    
    if issues['no_service']:
        print(f"ℹ️  No service: {len(issues['no_service'])} (this is OK)")
        print()
        sys.stdout.flush()
    
    if issues['no_date']:
        print(f"ℹ️  No date: {len(issues['no_date'])} (from unmentioned VCF files)")
        print()
        sys.stdout.flush()
    
    if issues['invalid_phones']:
        print(f"⚠️  Suspicious phone numbers: {len(issues['invalid_phones'])}")
        for rec in issues['invalid_phones'][:5]:
            print(f"   - \"{rec.get('name')}\": {rec.get('phone')}")
        if len(issues['invalid_phones']) > 5:
            print(f"   ... and {len(issues['invalid_phones']) - 5} more")
        print()
        sys.stdout.flush()
    
    # Summary
    total_issues = sum(len(v) for k, v in issues.items() if k not in ['no_service', 'no_date'])
    print(f"=== SUMMARY ===")
    print(f"Total recommendations: {len(data)}")
    print(f"Items with issues: {total_issues}")
    sys.stdout.flush()


if __name__ == '__main__':
    analyze_recommendations()

