#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean up recommendations.json by removing entries with invalid names (URL parameters, etc.)
"""

import json
import re
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from extract_recommendations import is_valid_name


def cleanup_recommendations(input_file: Path, output_file: Path = None):
    """Clean up recommendations by removing or fixing entries with invalid names."""
    if output_file is None:
        output_file = input_file
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        recommendations = json.load(f)
    
    print(f"Found {len(recommendations)} recommendations")
    
    cleaned = []
    removed = []
    fixed = []
    
    for rec in recommendations:
        name = rec.get('name', '')
        original_name = name
        
        # Clean name (remove newlines, normalize whitespace)
        if name:
            name = name.replace('\n', ' ').strip()
            name = re.sub(r'\s+', ' ', name)  # Normalize multiple spaces
        
        # Skip if name is invalid (URL-like, personal contacts, etc.)
        # But only if it's truly invalid - don't remove entries with just formatting issues
        if name and not is_valid_name(name):
            # Only remove if it's a personal contact or clearly invalid
            # Keep entries with phone/service even if name is invalid
            if name == 'Unknown' or (rec.get('phone') or rec.get('service')):
                # Keep the entry but mark name as Unknown if it's truly invalid
                if name != 'Unknown':
                    rec['name'] = 'Unknown'
                    fixed.append({
                        'old_name': original_name,
                        'new_name': 'Unknown',
                        'phone': rec.get('phone'),
                        'service': rec.get('service')
                    })
                cleaned.append(rec)
            else:
                # Remove entries with no valid name, phone, or service
                removed.append({
                    'name': original_name,
                    'phone': rec.get('phone'),
                    'service': rec.get('service')
                })
            continue
        
        # If name was cleaned, update it
        if name != original_name and name:
            rec['name'] = name
            fixed.append({
                'old_name': original_name,
                'new_name': name,
                'phone': rec.get('phone'),
                'service': rec.get('service')
            })
        
        cleaned.append(rec)
    
    print(f"\nCleaned up:")
    print(f"  - Fixed: {len(fixed)} entries (set name to 'Unknown')")
    print(f"  - Removed: {len(removed)} entries")
    print(f"  - Final count: {len(cleaned)} recommendations")
    
    if fixed:
        print(f"\nFixed entries:")
        for fix in fixed[:5]:  # Show first 5
            print(f"  - '{fix['old_name'][:50]}...' -> 'Unknown' (phone: {fix['phone']})")
        if len(fixed) > 5:
            print(f"  ... and {len(fixed) - 5} more")
    
    if removed:
        print(f"\nRemoved entries:")
        for rem in removed[:5]:  # Show first 5
            print(f"  - '{rem['name'][:50]}...' (phone: {rem['phone']})")
        if len(removed) > 5:
            print(f"  ... and {len(removed) - 5} more")
    
    print(f"\nWriting cleaned data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Saved {len(cleaned)} cleaned recommendations.")


if __name__ == '__main__':
    # Get project root (parent of src/)
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'web' / 'recommendations.json'
    cleanup_recommendations(input_file)

