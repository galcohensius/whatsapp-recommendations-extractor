#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix common issues in recommendations.json:
1. Remove true duplicates (same name, phone)
2. Clean service field text (remove conversational prefixes)
3. Remove entries with invalid phone numbers (< 7 digits)
4. Clean and fix invalid names (URL parameters, newlines, etc.)
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from extract_txt_and_vcf import is_valid_name, extract_service_from_name, clean_name_after_service_extraction


def clean_context_text(context: str) -> str:
    """Clean context field to remove unwanted patterns."""
    if not context:
        return context
    
    cleaned = context
    
    # Remove "vcf (file attached)" patterns
    cleaned = re.sub(r'\.vcf\s*\(file attached\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\(file attached\)', '', cleaned, flags=re.IGNORECASE)
    
    # Remove truecaller.com URLs
    cleaned = re.sub(r'https?://[^\s]*truecaller\.com[^\s]*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'truecaller\.com/[^\s]*', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up multiple spaces and periods
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\.\s*\.', '.', cleaned)
    cleaned = re.sub(r'\s*\.\s*$', '', cleaned)
    
    return cleaned.strip()


def clean_service_text(service: str) -> str:
    """Clean service field to remove conversational prefixes."""
    if not service:
        return service
    
    # Remove common Hebrew prefixes
    patterns = [
        r'^למישהו\s+המלצה\s+על?\s*',
        r'^למישהו\s+איש\s+',
        r'^למישהו\s+',
        r'^מישהו\s+',
        r'^המלצה\s+על?\s*',
        r'^המלצות?\s*',
        r'^למישהו\s+במקרה\s+',
    ]
    
    cleaned = service
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove trailing conversational suffixes
    cleaned = re.sub(r'\s+מניסיון.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+מומלץ.*$', '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()


def fix_recommendations(input_file: Path, output_file: Optional[Path] = None) -> Dict:
    """Fix issues in recommendations.json."""
    if output_file is None:
        output_file = input_file
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        recommendations = json.load(f)
    
    print(f"Found {len(recommendations)} recommendations")
    
    # Step 1: Remove duplicates (same name + phone, keeping the one with most info)
    print("\nStep 1: Removing duplicates...")
    seen = {}
    unique_recs = []
    duplicates_removed = 0
    
    for rec in recommendations:
        # Use normalized phone as key (remove +, spaces, dashes)
        phone = rec.get('phone', '').strip()
        phone_normalized = re.sub(r'[\s+\-()]', '', phone)
        name = rec.get('name', '').strip()
        
        key = (name.lower(), phone_normalized)
        
        if key in seen:
            # Check if this one has more information
            existing = seen[key]
            existing_info_score = (
                (1 if existing.get('service') else 0) +
                (1 if existing.get('context') and len(existing.get('context', '')) > 20 else 0) +
                (1 if existing.get('date') else 0)
            )
            new_info_score = (
                (1 if rec.get('service') else 0) +
                (1 if rec.get('context') and len(rec.get('context', '')) > 20 else 0) +
                (1 if rec.get('date') else 0)
            )
            
            if new_info_score > existing_info_score:
                # Replace with better one
                unique_recs.remove(existing)
                unique_recs.append(rec)
                seen[key] = rec
            duplicates_removed += 1
        else:
            seen[key] = rec
            unique_recs.append(rec)
    
    print(f"  Removed {duplicates_removed} duplicates")
    print(f"  Unique recommendations: {len(unique_recs)}")
    
    # Step 2: Clean service fields
    print("\nStep 2: Cleaning service fields...")
    services_cleaned = 0
    
    for rec in unique_recs:
        service = rec.get('service')
        if service and isinstance(service, str):
            cleaned = clean_service_text(service)
            if cleaned != service:
                rec['service'] = cleaned if cleaned else None
                services_cleaned += 1
    
    print(f"  Cleaned {services_cleaned} service fields")
    
    # Step 2.5: Clean context fields (remove vcf/file attached and truecaller URLs)
    print("\nStep 2.5: Cleaning context fields...")
    contexts_cleaned = 0
    
    for rec in unique_recs:
        context = rec.get('context')
        if context and isinstance(context, str):
            cleaned = clean_context_text(context)
            if cleaned != context:
                rec['context'] = cleaned if cleaned else None
                contexts_cleaned += 1
    
    print(f"  Cleaned {contexts_cleaned} context fields")
    
    # Step 2.6: Extract services from names for entries with null service
    print("\nStep 2.6: Extracting services from names...")
    services_extracted = 0
    
    for rec in unique_recs:
        # Only process entries with null service
        if not rec.get('service'):
            name = rec.get('name', '').strip()
            if name and name != 'Unknown':
                # Try to extract service from name
                service = extract_service_from_name(name)
                if service:
                    # Extract service and clean the name
                    rec['service'] = service
                    cleaned_name = clean_name_after_service_extraction(name, service)
                    if cleaned_name and cleaned_name != name:
                        rec['name'] = cleaned_name
                    services_extracted += 1
    
    print(f"  Extracted services from {services_extracted} names")
    
    # Step 3: Clean and fix names
    print("\nStep 3: Cleaning names...")
    names_fixed = 0
    names_set_to_unknown = 0
    
    for rec in unique_recs:
        name = rec.get('name', '')
        original_name = name
        
        if name:
            # Clean name (remove newlines, normalize whitespace)
            name = name.replace('\n', ' ').strip()
            name = re.sub(r'\s+', ' ', name)  # Normalize multiple spaces
            
            # If name is invalid (URL-like, personal contacts, etc.), set to Unknown
            if name and not is_valid_name(name):
                if name != 'Unknown':
                    rec['name'] = 'Unknown'
                    names_set_to_unknown += 1
            elif name != original_name:
                # Name was cleaned but is still valid
                rec['name'] = name
                names_fixed += 1
    
    print(f"  Fixed {names_fixed} names (normalized whitespace)")
    print(f"  Set {names_set_to_unknown} invalid names to 'Unknown'")
    
    # Step 4: Remove entries with invalid phone numbers (< 7 digits)
    print("\nStep 4: Checking phone numbers...")
    removed_entries = []
    phones_removed = 0
    
    # Function to count digits in phone number (ignoring formatting)
    def count_digits(phone: str) -> int:
        if not phone:
            return 0
        return len(re.sub(r'[^\d]', '', phone))
    
    valid_recs = []
    for rec in unique_recs:
        phone = rec.get('phone', '').strip()
        if not phone:
            # No phone at all - keep it (might be valid)
            valid_recs.append(rec)
            continue
        
        digit_count = count_digits(phone)
        
        if digit_count < 7:
            # Invalid phone - remove entry
            removed_entries.append({
                'name': rec.get('name'),
                'phone': phone,
                'digits': digit_count
            })
            phones_removed += 1
        else:
            valid_recs.append(rec)
    
    unique_recs = valid_recs
    
    if phones_removed > 0:
        print(f"  Removed {phones_removed} entries with invalid phone numbers (< 7 digits):")
        for entry in removed_entries[:5]:  # Show first 5
            print(f"    - '{entry['name']}': {entry['phone']} ({entry['digits']} digits)")
        if len(removed_entries) > 5:
            print(f"    ... and {len(removed_entries) - 5} more")
    else:
        print("  All phone numbers are valid (≥ 7 digits)")
    
    # Save fixed recommendations
    print(f"\nSaving to {output_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_recs, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Saved {len(unique_recs)} recommendations")
    
    return {
        'total_before': len(recommendations),
        'total_after': len(unique_recs),
        'duplicates_removed': duplicates_removed,
        'services_cleaned': services_cleaned,
        'services_extracted': services_extracted,
        'names_fixed': names_fixed,
        'names_set_to_unknown': names_set_to_unknown,
        'phones_removed': phones_removed
    }


if __name__ == '__main__':
    import sys
    
    # Get project root
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'web' / 'recommendations.json'
    
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    
    output_file = input_file  # Overwrite by default
    
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    result = fix_recommendations(input_file, output_file)
    
    print("\n" + "="*50)
    print("Summary:")
    print(f"  Before: {result['total_before']} recommendations")
    print(f"  After: {result['total_after']} recommendations")
    print(f"  Duplicates removed: {result['duplicates_removed']}")
    print(f"  Services cleaned: {result['services_cleaned']}")
    print(f"  Services extracted from names: {result['services_extracted']}")
    print(f"  Names fixed: {result['names_fixed']}")
    print(f"  Names set to Unknown: {result['names_set_to_unknown']}")
    print(f"  Entries removed (invalid phones): {result['phones_removed']}")
    print("="*50)

