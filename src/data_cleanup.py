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
from typing import Dict, List, Optional, Tuple

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
    """Clean service field to remove conversational prefixes and extract just the service name.
    
    Examples:
    - "לכם המלצה על מוביל טוב" -> "מוביל"
    - "המלצה על X" -> "X"
    - "המלצה לנגר" -> "נגר"
    - "למשהו מספר של חשמלאי" -> "חשמלאי"
    - "מספר טלפון של שיפוצניק" -> "שיפוצניק"
    - "במקרה נהג מונית..." -> "נהג מונית"
    """
    if not service:
        return service
    
    # If service is very long (>100 chars), try to extract first meaningful service keyword
    # This handles cases like "בבקשה המלצות ל 2 בעלי מקצוע איש מזגנים..."
    if len(service) > 100:
        # Try to find service keywords in the text
        service_keywords = [
            r'אינסטלטור', r'חשמלאי', r'גנן', r'נגר', r'מזגנים?', r'דוד\s+שמש',
            r'מוביל', r'נהג\s+מונית', r'קבלן', r'שיפוצניק', r'מסגר', r'אלומיניום',
            r'טכנאי\s+\S+', r'מתקין\s+\S+', r'מדביר', r'ריסוס', r'דלתות',
        ]
        for keyword_pattern in service_keywords:
            match = re.search(keyword_pattern, service, re.IGNORECASE)
            if match:
                return match.group(0).strip()
    
    # First, try to extract service from patterns like "לכם המלצה על X" or "לכם המלצה על X טוב"
    # Pattern: "לכם המלצה על [service] [optional adjective]"
    pattern_full = r'^לכם\s+המלצה\s+על\s+([^\s]+(?:\s+[^\s]+)?)(?:\s+טוב|\s+מעולה|\s+מצוין)?\s*$'
    match = re.search(pattern_full, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: "המלצה ל[service]" or "המלצה לנגר" -> extract service
    # This handles: "המלצה לנגר", "המלצה לטכנאי מזגנים", "המלצה למדביר", etc.
    pattern_simple_recommendation = r'^המלצה\s+ל([^\s]+(?:\s+[^\s]+)?(?:\s+[^\s]+)?)(?:\s+טוב|\s+מעולה|\s+מצוין|\s+אמין|\s+מקצועי|\s+מסודר|\s+.*)?\s*$'
    match = re.search(pattern_simple_recommendation, service, re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        # Remove trailing adjectives, descriptive text, and conversational words
        extracted = re.sub(r'\s+(טוב|מעולה|מצוין|נהדר|מצויין|אמין|מקצועי|מסודר|מקצוען|טוב\s+וישר|תודה|המלצה|דחוף|לסייע\s+לי).*$', '', extracted, flags=re.IGNORECASE)
        # Remove very long trailing text (keep only first 30 chars if too long)
        if len(extracted) > 30:
            words = extracted.split()
            # Take first 2-3 words max
            extracted = ' '.join(words[:3])
        if len(extracted) >= 2:
            return extracted
    
    # Pattern: "המלצה [service]" (without ל) -> extract service
    pattern_recommendation_no_lamed = r'^המלצה\s+([^\s]+(?:\s+[^\s]+)?)(?:\s+תודה|\s+.*)?\s*$'
    match = re.search(pattern_recommendation_no_lamed, service, re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        # Remove trailing conversational words
        extracted = re.sub(r'\s+(תודה|המלצה|דחוף|לסייע\s+לי).*$', '', extracted, flags=re.IGNORECASE)
        if len(extracted) >= 2:
            return extracted
    
    # Pattern: "לכם המלצה על [service]"
    pattern_simple = r'^לכם\s+המלצה\s+על\s+(.+?)\s*$'
    match = re.search(pattern_simple, service, re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        # Remove trailing adjectives like "טוב", "מעולה", "מצוין"
        extracted = re.sub(r'\s+(טוב|מעולה|מצוין|נהדר|מצויין|אמין|מקצועי|מסודר|מקצוען)\s*$', '', extracted, flags=re.IGNORECASE)
        return extracted
    
    # Pattern: "למשהו מספר של [service]" -> extract service
    pattern_phone_request = r'^למשהו\s+מספר\s+של\s+([^\s]+(?:\s+[^\s]+)?)\s*$'
    match = re.search(pattern_phone_request, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: "מספר טלפון של [service]" -> extract service
    pattern_phone_of = r'^מספר\s+טלפון\s+של\s+([^\s]+(?:\s+[^\s]+)?)\s*$'
    match = re.search(pattern_phone_of, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: "במקרה [service]..." -> extract service (e.g., "במקרה נהג מונית...")
    pattern_in_case = r'^במקרה\s+([^\s]+(?:\s+[^\s]+)?)(?:\s+.*)?$'
    match = re.search(pattern_in_case, service, re.IGNORECASE)
    if match:
        service_candidate = match.group(1).strip()
        # Check if it's a valid service (not just "כלוב" or other non-service words)
        service_keywords = [r'נהג\s+מונית', r'מוביל', r'טכנאי', r'מתקין', r'אינסטלטור', r'חשמלאי']
        for keyword in service_keywords:
            if re.search(keyword, service_candidate, re.IGNORECASE):
                # Extract the full service phrase
                full_match = re.search(keyword + r'(?:\s+\S+)*', service, re.IGNORECASE)
                if full_match:
                    return full_match.group(0).strip()
        # If no service keyword found, return the first part anyway if it's reasonable
        if len(service_candidate) >= 3 and len(service_candidate) < 30:
            return service_candidate
    
    # Pattern: "מקום שמוכר ומתקין [service]" -> extract service
    pattern_place_sells = r'^מקום\s+שמוכר\s+(?:ומתקין\s+)?([^\s]+(?:\s+[^\s]+)?)\s*$'
    match = re.search(pattern_place_sells, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: "מקצוע [service]" or "מקצוע טוב ל[service]" -> extract service
    pattern_profession = r'^מקצוע\s+(?:טוב\s+ל)?([^\s]+(?:\s+[^\s]+)?)(?:\s+.*)?$'
    match = re.search(pattern_profession, service, re.IGNORECASE)
    if match:
        service_candidate = match.group(1).strip()
        if len(service_candidate) >= 2 and len(service_candidate) < 50:
            return service_candidate
    
    # Pattern: "שמטפל ב[service]" -> extract service
    pattern_treats = r'^שמטפל\s+ב([^\s]+(?:\s+[^\s]+)?)\s*$'
    match = re.search(pattern_treats, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: "שמתקן [service]" -> extract service
    pattern_fixes = r'^שמתקן\s+(?:מתעסק\s+עם\s+)?([^\s]+(?:\s+[^\s]+)?)\s*$'
    match = re.search(pattern_fixes, service, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Remove common Hebrew prefixes
    patterns = [
        r'^למישהו\s+המלצה\s+על?\s*',
        r'^למישהו\s+איש\s+',
        r'^למישהו\s+',
        r'^מישהו\s+',
        r'^המלצה\s+על?\s*',
        r'^המלצה\s+טובה\s+ל',
        r'^המלצות?\s*',
        r'^למישהו\s+במקרה\s+',
        r'^מומלץ\s+',
        r'^בסופו\s+של\s+יום\s+ב\s+\d+\s+שח\s+מקבלים\s+מה\s+שעולה\s+פה\s+\d+\s*',  # Remove price comparison text
        r'^רלוונטי\s*$',  # "רלוונטי" alone should be cleaned (but might need context)
        r'^מקום\s+ש',  # "מקום ש" (place that)
        r'^מקום\s+שמוכר\s+ומתקין\s+',  # "מקום שמוכר ומתקין" (place that sells and installs)
        r'^מקום\s+שמוכר\s+',  # "מקום שמוכר" (place that sells)
        r'^מספר\s+טלפון\s+',  # "מספר טלפון" (phone number)
        r'^מקצוע\s+',  # "מקצוע" (profession)
        r'^מקצוענות\s+',  # "מקצוענות" (professionalism)
        r'^דחוף\s*',  # "דחוף" (urgent) at start
        r'https?://[^\s]*',  # URLs starting with http/https
    ]
    
    cleaned = service
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove trailing conversational suffixes
    cleaned = re.sub(r'\s+מניסיון.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+מומלץ.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+(טוב|מעולה|מצוין|נהדר|מצויין|אמין|מקצועי|מסודר|מקצוען)\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+דחוף\s*$', '', cleaned, flags=re.IGNORECASE)  # "דחוף" at end
    cleaned = re.sub(r'\s+לסייע\s+לי\s*$', '', cleaned, flags=re.IGNORECASE)  # "לסייע לי" at end
    cleaned = re.sub(r'\s+תודה\s*$', '', cleaned, flags=re.IGNORECASE)  # "תודה" at end
    cleaned = re.sub(r'\s+המלצה\s*$', '', cleaned, flags=re.IGNORECASE)  # "המלצה" at end
    cleaned = re.sub(r'\s+מקצוענות\s*$', '', cleaned, flags=re.IGNORECASE)  # "מקצוענות" at end
    cleaned = re.sub(r'\s+מקצוע\s*$', '', cleaned, flags=re.IGNORECASE)  # "מקצוע" at end
    cleaned = re.sub(r'\s+https?://[^\s]*', '', cleaned, flags=re.IGNORECASE)  # URLs anywhere
    
    # Remove very long descriptive text at the end (keep first 50 chars if result is too long)
    cleaned = cleaned.strip()
    if len(cleaned) > 50:
        # Try to find a service keyword in the first part
        words = cleaned.split()
        if len(words) > 5:
            # Take first few words that might be the service
            for i in range(1, min(5, len(words))):
                candidate = ' '.join(words[:i])
                if len(candidate) <= 30:
                    # Check if it contains a service keyword
                    service_keywords = [r'טכנאי', r'מתקין', r'אינסטלטור', r'חשמלאי', r'גנן', r'נגר', r'מוביל', r'קבלן']
                    for keyword in service_keywords:
                        if re.search(keyword, candidate, re.IGNORECASE):
                            return candidate
            # If no service keyword found, just return first 3-4 words
            return ' '.join(words[:4])
    
    return cleaned.strip()


def is_personal_contact_only(rec: Dict, messages: Optional[List[Dict]] = None) -> bool:
    """Check if a recommendation is a personal contact (friend/family) without service provider intent.
    
    Only returns True if BOTH conditions are met:
    1. Service field is null (no service extracted)
    2. Context suggests personal relationship without service provider intent
    
    Important: If service field exists (even if it mentions friend/family), keep the entry - 
    service providers can be friends/family.
    
    Args:
        rec: Recommendation dictionary
        messages: Optional list of all messages for context lookup (if available)
    
    Returns:
        True if it's clearly a personal contact recommendation, not a service provider
    """
    # If service exists, keep it - service providers can be friends/family
    if rec.get('service'):
        return False
    
    # Get context from recommendation (handle None values)
    context = (rec.get('context') or '').lower()
    name = (rec.get('name') or '').lower()
    
    # Personal relationship keywords (Hebrew)
    personal_keywords = [
        'חבר', 'חברה', 'חברים', 'חברות',  # friend(s)
        'ידיד', 'ידידה', 'ידידים',  # friend(s)
        'אבא', 'אמא', 'אב', 'אם',  # dad, mom
        'אח', 'אחות', 'אחים', 'אחיות',  # brother(s), sister(s)
        'בן', 'בת', 'ילדים',  # son, daughter, children
        'משפחה', 'קרוב', 'קרובה', 'קרובים',  # family, relative(s)
    ]
    
    # Service-related keywords (Hebrew) - if these appear, it's likely a service provider
    service_keywords = [
        'מומלץ', 'ממליץ', 'ממליצה', 'המלצה',  # recommended, recommendation
        'עובד', 'עובדת', 'עובדים',  # worker(s)
        'נותן שירות', 'נותנת שירות', 'נותני שירות',  # service provider(s)
        'שירות', 'עבודה', 'עבודות',  # service, work
        'מקצוע', 'מקצועי', 'מקצועית',  # profession, professional
        'טכנאי', 'טכנאית',  # technician
        'איש מקצוע', 'אשת מקצוע',  # professional
        'ביצע', 'עשה', 'עשתה',  # performed, did
        'תיקון', 'תיקונים', 'תיקן', 'תיקנה',  # repair(s), repaired
        'התקנה', 'התקנות', 'התקין', 'התקינה',  # installation(s), installed
    ]
    
    # Check if context contains personal relationship keywords
    has_personal_keyword = any(keyword in context or keyword in name for keyword in personal_keywords)
    
    # Check if context contains service-related keywords
    has_service_keyword = any(keyword in context for keyword in service_keywords)
    
    # Only mark as personal contact if:
    # 1. Service is null (already checked above)
    # 2. Has personal relationship keyword
    # 3. Lacks service-related keywords
    if has_personal_keyword and not has_service_keyword:
        return True
    
    return False


def pre_enhancement_cleanup(recommendations: List[Dict], messages: Optional[List[Dict]] = None) -> Tuple[List[Dict], Dict]:
    """Clean recommendations before AI enhancement.
    
    Returns:
        Tuple of (cleaned_recommendations, stats_dict)
    """
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
    
    # Step 2.7: Remove invalid recommendations (URL fragments, invalid names, etc.)
    print("\nStep 2.7: Filtering invalid recommendations...")
    invalid_removed = 0
    filtered_recs = []
    
    non_name_words = ['https', 'http', 'www', 'com', 'book', 'location', 'maps', 
                     'posts', 'story', 'reel', 'video', 'watch', 'unknown']
    
    for rec in unique_recs:
        name = rec.get('name', '').strip()
        phone = rec.get('phone', '').strip()
        
        # Skip if name is a known non-name word
        if name:
            name_lower = name.lower()
            if name_lower in non_name_words:
                invalid_removed += 1
                continue
            
            # Skip if name looks like URL fragment
            if any(name_lower.startswith(word + '/') or name_lower.startswith(word + '.') 
                   for word in ['com', 'www', 'http', 'https', 'maps', 'posts', 'story', 'reel']):
                invalid_removed += 1
                continue
            
            # Skip if name is invalid
            if not is_valid_name(name):
                invalid_removed += 1
                continue
        
        # Skip if phone doesn't look like a valid Israeli phone
        if phone:
            phone_clean = re.sub(r'[^\d+]', '', phone)
            # Must start with 0, +972, or 972 for Israeli numbers
            if not (phone_clean.startswith('0') or phone_clean.startswith('+972') or 
                   (phone_clean.startswith('972') and len(phone_clean) >= 12)):
                # Check digit count
                digits_only = re.sub(r'[^\d]', '', phone)
                if len(digits_only) < 9 or len(digits_only) > 10:
                    invalid_removed += 1
                    continue
                # If name suggests URL, skip it
                if name and any(word in name.lower() for word in ['http', 'www', 'com', 'posts', 'story', 'reel', 'maps']):
                    invalid_removed += 1
                    continue
        
        filtered_recs.append(rec)
    
    unique_recs = filtered_recs
    print(f"  Removed {invalid_removed} invalid recommendations")
    print(f"  Valid recommendations: {len(unique_recs)}")
    
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
    
    # Step 5: Filter out personal contacts (friends/family without service provider intent)
    print("\nStep 5: Filtering personal contacts...")
    personal_contacts_removed = 0
    service_provider_recs = []
    
    for rec in unique_recs:
        if is_personal_contact_only(rec, messages):
            personal_contacts_removed += 1
        else:
            service_provider_recs.append(rec)
    
    unique_recs = service_provider_recs
    if personal_contacts_removed > 0:
        print(f"  Removed {personal_contacts_removed} personal contact entries (friends/family without service)")
    else:
        print("  No personal contacts to remove")
    
    stats = {
        'total_before': len(recommendations),
        'total_after': len(unique_recs),
        'duplicates_removed': duplicates_removed,
        'services_cleaned': services_cleaned,
        'names_fixed': names_fixed,
        'names_set_to_unknown': names_set_to_unknown,
        'phones_removed': phones_removed,
        'personal_contacts_removed': personal_contacts_removed,
        'contexts_cleaned': contexts_cleaned,
        'invalid_removed': invalid_removed
    }
    
    return unique_recs, stats


def post_enhancement_cleanup(recommendations: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Final cleanup after AI enhancement.
    
    Returns:
        Tuple of (cleaned_recommendations, stats_dict)
    """
    print(f"Found {len(recommendations)} recommendations")
    
    # Step 1: Clean service fields again (in case AI added prefixes)
    print("\nStep 1: Final service field cleaning...")
    services_cleaned = 0
    
    for rec in recommendations:
        service = rec.get('service')
        if service and isinstance(service, str):
            cleaned = clean_service_text(service)
            if cleaned != service:
                rec['service'] = cleaned if cleaned else None
                services_cleaned += 1
    
    print(f"  Cleaned {services_cleaned} service fields")
    
    # Step 2: Clean context fields again (remove any new issues)
    print("\nStep 2: Final context field cleaning...")
    contexts_cleaned = 0
    
    for rec in recommendations:
        context = rec.get('context')
        if context and isinstance(context, str):
            cleaned = clean_context_text(context)
            if cleaned != context:
                rec['context'] = cleaned if cleaned else None
                contexts_cleaned += 1
    
    print(f"  Cleaned {contexts_cleaned} context fields")
    
    # Step 3: Remove entries that still have null service after AI enhancement
    print("\nStep 3: Removing entries with null service...")
    before_count = len(recommendations)
    final_recs = [rec for rec in recommendations if rec.get('service')]
    null_services_removed = before_count - len(final_recs)
    
    if null_services_removed > 0:
        print(f"  Removed {null_services_removed} entries with null service")
    else:
        print("  All entries have service")
    
    stats = {
        'total_before': before_count,
        'total_after': len(final_recs),
        'services_cleaned': services_cleaned,
        'contexts_cleaned': contexts_cleaned,
        'null_services_removed': null_services_removed
    }
    
    return final_recs, stats


def fix_recommendations(input_file: Path, output_file: Optional[Path] = None, messages: Optional[List[Dict]] = None) -> Dict:
    """Fix issues in recommendations.json (legacy function for backward compatibility).
    
    This function now calls pre_enhancement_cleanup for the full cleanup.
    """
    if output_file is None:
        output_file = input_file
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        recommendations = json.load(f)
    
    # Use pre_enhancement_cleanup for full cleanup
    unique_recs, stats = pre_enhancement_cleanup(recommendations, messages)
    
    # Save fixed recommendations
    print(f"\nSaving to {output_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_recs, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Saved {len(unique_recs)} recommendations")
    
    # Add services_extracted=0 for backward compatibility (now done in extraction)
    stats['services_extracted'] = 0
    
    return stats


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
    print(f"  Personal contacts removed: {result.get('personal_contacts_removed', 0)}")
    print("="*50)

