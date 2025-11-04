#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract recommendations from WhatsApp chat and .vcf contact files.
Outputs a JSON file with all recommendations.
"""

import re
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_phone, extract_phone_numbers
from analyze_recommendations import analyze_recommendations



def extract_service_from_name(name: str) -> Optional[str]:
    """Extract service from name field if it contains 'Name - Service' pattern.
    
    Examples:
        'דויד - מתקין מזגנים' -> 'מתקין מזגנים'
        'John - Plumber' -> 'Plumber'
    """
    if not name:
        return None
    
    # Pattern: Name - Service (supports -, –, —, and variations)
    patterns = [
        r'^([^\-–—]+?)\s*[-–—]\s*(.+)$',  # Name - Service
        r'^(.+?)\s*[-–—]\s*(.+)$',         # More flexible
    ]
    
    for pattern in patterns:
        match = re.match(pattern, name.strip())
        if match:
            name_part = match.group(1).strip()
            service_part = match.group(2).strip()
            
            # Validate: service should be meaningful (at least 3 chars)
            if len(service_part) >= 3 and len(name_part) >= 2:
                return service_part
    
    return None


def extract_service_from_filename(filename: str, name: Optional[str] = None) -> Optional[str]:
    """Intelligently extract service/category from filename.
    
    Handles patterns like:
    - 'Name - Service.vcf' -> 'Service'
    - 'Service - Name.vcf' -> 'Service'
    - 'Name.vcf' (with name known) -> remaining text after removing name
    """
    filename_stem = Path(filename).stem  # Remove .vcf extension
    
    # First, try to detect "Name - Service" or "Service - Name" patterns
    dash_patterns = [
        r'^([^\-–—]+?)\s*[-–—]\s*(.+)$',  # Name - Service
        r'^(.+?)\s*[-–—]\s*([^\-–—]+?)$',  # Service - Name
    ]
    
    for pattern in dash_patterns:
        match = re.match(pattern, filename_stem)
        if match:
            part1 = match.group(1).strip()
            part2 = match.group(2).strip()
            
            # If we have the name, determine which part is the service
            if name:
                name_clean = name.strip().lower()
                # Check which part matches the name
                if part1.lower() == name_clean or part1.lower().startswith(name_clean[:3]):
                    # part1 is name, part2 is service
                    if len(part2) >= 3:
                        return part2
                elif part2.lower() == name_clean or part2.lower().startswith(name_clean[:3]):
                    # part2 is name, part1 is service
                    if len(part1) >= 3:
                        return part1
                else:
                    # Can't match name, assume longer part is service
                    if len(part1) >= 3 and len(part1) > len(part2):
                        return part1
                    elif len(part2) >= 3:
                        return part2
            else:
                # No name provided, assume longer part is service
                if len(part1) >= 3 and len(part1) > len(part2):
                    return part1
                elif len(part2) >= 3:
                    return part2
    
    # Fallback: Remove the person's name from filename if provided
    text_to_search = filename_stem
    if name:
        # Try to remove name (might be in different positions)
        name_variations = [
            name,
            name.replace(' ', ''),
            name.replace('.', ''),
            name.replace(' ', '.'),
            name.replace('.', ' '),
        ]
        for name_var in name_variations:
            # Remove name and surrounding dots/spaces
            text_to_search = re.sub(re.escape(name_var), '', text_to_search, flags=re.IGNORECASE)
            text_to_search = re.sub(r'[.\s]+', ' ', text_to_search).strip()
    
    # Clean up: remove common separators and normalize spaces
    text_to_search = re.sub(r'[.\-_]+', ' ', text_to_search)
    text_to_search = re.sub(r'\s+', ' ', text_to_search).strip()
    
    # Return remaining text if it's meaningful (likely the service)
    if text_to_search and len(text_to_search) >= 3:
        # Make sure it's not just the name again
        if not name or text_to_search.lower() != name.lower():
            return text_to_search
    
    return None


def extract_sender_phone(sender: str) -> str:
    """Extract and normalize phone number from sender field.
    
    The sender field can be:
    - A phone number (e.g., '+972 52-577-4739', '050-1234567')
    - A contact name (if WhatsApp shows contact name)
    - Something else
    
    Returns the normalized phone number if found, otherwise returns sender as-is.
    """
    # First, try to extract phone numbers from the sender field
    phones = extract_phone_numbers(sender)
    
    # If we found a phone number, normalize and return it
    if phones:
        return normalize_phone(phones[0])
    
    # If sender itself looks like a phone number (starts with + or digits), normalize it
    sender_clean = sender.strip()
    if sender_clean.startswith('+') or (sender_clean and sender_clean[0].isdigit()):
        normalized = normalize_phone(sender_clean)
        # Check if normalized looks like a valid phone number
        digits_only = re.sub(r'[^\d]', '', normalized)
        if len(digits_only) >= 9:  # At least 9 digits for a valid phone number
            return normalized
    
    # Otherwise, return sender as-is (might be a contact name)
    return sender


def parse_vcf_file(vcf_path: Path) -> Optional[Dict[str, Optional[str]]]:
    """Parse a .vcf file and extract name, phone, and infer service from filename."""
    try:
        with open(vcf_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract name from FN field (preferred) or N field (fallback)
        name = None
        name_match = re.search(r'FN:([^\r\n]+)', content)
        if name_match:
            name = name_match.group(1).strip()
        else:
            # Fallback: Try N: field (Name field - format: Family;Given;Additional;Prefix;Suffix)
            n_match = re.search(r'N:([^\r\n]+)', content)
            if n_match:
                n_parts = n_match.group(1).strip().split(';')
                # Combine parts (excluding empty parts) to form name
                name_parts = [p for p in n_parts if p]
                if name_parts:
                    name = ' '.join(name_parts).strip()
        
        # If still no name, try to extract from filename as last resort
        if not name:
            filename_stem = vcf_path.stem
            # Remove common patterns that aren't names
            name = re.sub(r'\.vcf$', '', filename_stem, flags=re.IGNORECASE)
            # Clean up: remove common service indicators
            name = re.sub(r'\s*[-–—]\s*.*$', '', name).strip()  # Remove " - Service" part
            if not name or len(name) < 2:
                name = None
        
        # Extract phone from TEL fields (handle various formats)
        phone = None
        tel_patterns = [
            r'TEL[^:]*:([+\d\s\-]+)',
            r'item\d+\.TEL[^:]*:([+\d\s\-]+)',
        ]
        for pattern in tel_patterns:
            phone_match = re.search(pattern, content)
            if phone_match:
                phone_raw = phone_match.group(1).strip()
                # Normalize phone number using utility function
                phone = normalize_phone(phone_raw)
                break
        
        # Intelligently extract service:
        # 1. First try from name field (e.g., "דויד - מתקין מזגנים")
        service = None
        if name:
            service = extract_service_from_name(name)
            # If service was extracted from name, clean the name
            if service:
                # Remove service part from name
                name_clean_patterns = [
                    r'^([^\-–—]+?)\s*[-–—]\s*.+$',  # Name - Service -> Name
                ]
                for pattern in name_clean_patterns:
                    match = re.match(pattern, name)
                    if match:
                        name = match.group(1).strip()
                        break
        
        # 2. If no service from name, try filename
        if not service:
            service = extract_service_from_filename(vcf_path.name, name)
        
        if name and phone:
            return {
                'name': name,
                'phone': phone,
                'service': service,
                'filename': vcf_path.name
            }
    except Exception as e:
        print(f"Error parsing {vcf_path}: {e}")
    return None


def parse_all_vcf_files(data_dir: Path) -> Dict[str, Dict]:
    """Parse all .vcf files and return a dict keyed by filename."""
    vcf_data = {}
    for vcf_file in data_dir.glob('*.vcf'):
        parsed = parse_vcf_file(vcf_file)
        if parsed:
            # Use filename (case-insensitive) as key
            vcf_data[vcf_file.name.lower()] = parsed
    return vcf_data


def extract_service_from_context(text: str, chat_message_index: Optional[int] = None, all_messages: Optional[List[Dict]] = None) -> Optional[str]:
    """Intelligently extract service/category from chat context.
    
    Looks for:
    1. Service mentions in the current message
    2. Questions asking for a service in previous messages (context-aware)
    3. Explicit service descriptions
    """
    # Common Hebrew question patterns asking for services
    question_patterns = [
        r'מישהו מכיר ([^?]+)\?',
        r'יש ([^?]+)\?',
        r'מחפש ([^?]+)',
        r'צריך ([^?]+)',
        r'המלצה ל([^?]+)',
        r'מי מכיר ([^?]+)',
    ]
    
    # First, check if there's a question in the current or recent messages
    if all_messages and chat_message_index is not None:
        # Look at current message and up to 2 previous messages
        for i in range(max(0, chat_message_index - 2), chat_message_index + 1):
            msg_text = all_messages[i]['text']
            for pattern in question_patterns:
                match = re.search(pattern, msg_text, re.IGNORECASE)
                if match:
                    service_candidate = match.group(1).strip()
                    # Clean up the candidate
                    service_candidate = re.sub(r'[^\w\sא-ת]', '', service_candidate).strip()
                    if len(service_candidate) >= 3:
                        return service_candidate
    
    # Look for explicit mentions like "מומלץ ל...", "המלצה ל..."
    explicit_patterns = [
        r'מומלץ ל([^\.\n]{3,30})',
        r'המלצה ל([^\.\n]{3,30})',
        r'איש ([^\.\n]{3,30})',
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            service = match.group(1).strip()
            # Clean up
            service = re.sub(r'[^\w\sא-ת]', '', service).strip()
            if len(service) >= 3:
                return service
    
    return None


def parse_whatsapp_chat(chat_file: Path) -> List[Dict]:
    """Parse WhatsApp chat file and extract messages with metadata."""
    messages = []
    
    with open(chat_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern for WhatsApp message format: DD/MM/YYYY, HH:MM - Sender: Message
    # Multi-line messages continue without this pattern
    message_pattern = re.compile(r'(\d{1,2}/\d{1,2}/\d{4}), (\d{1,2}:\d{2}) - ([^:]+): (.+?)(?=\n\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2} - |$)', re.DOTALL)
    
    matches = list(message_pattern.finditer(content))
    
    for i, match in enumerate(matches):
        date_str = match.group(1)
        time_str = match.group(2)
        sender = match.group(3).strip()
        message_text = match.group(4).strip()
        
        # Get full message including multi-line continuation
        start_pos = match.end(4)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)
        
        # Get continuation lines (lines that don't start with date pattern)
        continuation = content[start_pos:end_pos]
        full_message = message_text + continuation
        full_message = full_message.rstrip('\n')
        
        # Parse datetime - ensure we always get a date
        date_iso = None
        try:
            datetime_obj = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            date_iso = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Try alternative date format (MM/DD/YYYY if DD/MM/YYYY fails)
            try:
                datetime_obj = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M")
                date_iso = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                # If all parsing fails, use the raw date string as fallback
                date_iso = f"{date_str} {time_str}"
        
        messages.append({
            'date': date_iso,
            'sender': sender,
            'text': full_message,
            'raw_text': message_text
        })
    
    return messages


def parse_all_chat_files(text_dir: Path) -> List[Dict]:
    """Parse all .txt WhatsApp chat files and return a list of all messages."""
    all_messages = []
    
    if not text_dir.exists():
        print(f"  No chat files found in {text_dir}")
        return all_messages
    
    chat_files = list(text_dir.glob('*.txt'))
    if not chat_files:
        print(f"  No chat files found in {text_dir}")
        return all_messages
    
    for chat_file in chat_files:
        try:
            messages = parse_whatsapp_chat(chat_file)
            all_messages.extend(messages)
        except Exception as e:
            print(f"Error parsing {chat_file.name}: {e}")
    
    print(f"  Found {len(all_messages)} messages from chat files")
    
    return all_messages


def get_full_context_for_recommendation(rec: Dict, messages: List[Dict], context_window: int = 5) -> str:
    """Get full chat context for a recommendation.
    
    Args:
        rec: Recommendation dictionary with 'chat_message_index' field
        messages: List of all parsed messages
        context_window: Number of messages before and after to include (default: 5)
    
    Returns:
        Formatted string with full context, or original context if chat_message_index is None
    """
    chat_message_index = rec.get('chat_message_index')
    
    # If no message index (e.g., unmentioned VCF files), return original context
    if chat_message_index is None:
        return rec.get('context', '')
    
    # Ensure chat_message_index is valid
    if chat_message_index < 0 or chat_message_index >= len(messages):
        return rec.get('context', '')
    
    # Get surrounding messages
    start_idx = max(0, chat_message_index - context_window)
    end_idx = min(len(messages), chat_message_index + context_window + 1)
    
    context_messages = []
    for i in range(start_idx, end_idx):
        msg = messages[i]
        date_str = msg.get('date', 'Unknown date')
        sender = msg.get('sender', 'Unknown sender')
        text = msg.get('text', '')
        
        # Mark the message that contains the recommendation
        marker = ">>> " if i == chat_message_index else "    "
        context_messages.append(f"{marker}[{date_str}] {sender}: {text}")
    
    return "\n".join(context_messages)


def is_valid_name(name: str) -> bool:
    """Validate that a name candidate is not a URL, URL parameter, personal contact, or other non-name string."""
    if not name or len(name) < 2:
        return False
    
    # Clean name (remove newlines, normalize whitespace)
    name = name.replace('\n', ' ').strip()
    
    # Personal contacts that shouldn't be recommendations
    personal_contacts = ['אבא', 'אמא', 'אבא של', 'אמא של', 'אח', 'אחות', 'אח של', 'אחות של']
    if name in personal_contacts:
        return False
    
    # Check for URL-like patterns
    url_indicators = [
        r'^https?://',  # URL protocol
        r'^www\.',      # www. prefix
        r'\.(com|net|org|co\.il|gov)',  # Domain extensions
        r'[?&]',        # URL query parameters
        r'=',           # URL parameters (key=value)
        r'%[0-9A-Fa-f]{2}',  # URL encoding
        r'gclid=',      # Google Ads tracking
        r'fbid=',       # Facebook ID
        r'campaignid=', # Campaign ID
        r'gad_source=', # Google Ads source
        r'gbraid=',     # Google Ads tracking
        r'utm_',        # UTM parameters
        r'story_fbid',  # Facebook story ID
    ]
    
    name_lower = name.lower()
    
    # Check for URL indicators
    for pattern in url_indicators:
        if re.search(pattern, name_lower):
            return False
    
    # Check if it looks like URL parameters (contains multiple = or &)
    if name.count('=') > 0 or name.count('&') > 0:
        # Allow single = only if it's clearly not a URL (e.g., "Name=Value" would be suspicious)
        if name.count('&') > 0 or (name.count('=') > 0 and ('&' in name or '?' in name)):
            return False
    
    # Check if it's mostly alphanumeric with special URL-like characters
    # Names shouldn't have too many special characters unless they're punctuation
    non_name_chars = sum(1 for c in name if c in '=?&/%#')
    if non_name_chars > 2:  # Too many URL-like characters
        return False
    
    # If it starts with common URL parameter prefixes, reject it
    if re.match(r'^(gad_|utm_|gclid|fbid|campaignid|gbraid)', name_lower):
        return False
    
    return True


def extract_text_recommendations(messages: List[Dict], vcf_data: Dict) -> List[Dict]:
    """Extract recommendations from chat text (name + phone patterns)."""
    recommendations = []
    
    for idx, msg in enumerate(messages):
        text = msg['text']
        
        # Skip system messages
        if any(keyword in msg['sender'].lower() for keyword in ['system', 'messages and calls', 'created group', 'joined', 'left', 'added', 'removed', 'changed']):
            continue
        
        # Extract phone numbers
        phones = extract_phone_numbers(text)
        
        if not phones:
            continue
        
        # Try to find names near phone numbers
        # Look for patterns like: "Name" followed by phone, or phone followed by "Name"
        for phone in phones:
            # Find context around the phone number
            phone_pos = text.find(phone)
            if phone_pos == -1:
                continue
            
            # Get context (100 chars before and after)
            start = max(0, phone_pos - 100)
            end = min(len(text), phone_pos + len(phone) + 100)
            context = text[start:end]
            
            # Try to extract name from context
            # Look for text before phone that might be a name (Hebrew or English, 2-30 chars)
            name = None
            before_phone = text[max(0, phone_pos - 50):phone_pos].strip()
            
            # Pattern: Look for words that might be names
            # Common patterns: "תתקשר ל..." (call to), "יש את..." (there is), name patterns
            name_patterns = [
                r'תתקשר ל([^.\n]{2,30}?)(?:\s*[.:,]|\s*$|\s+\d|\s*\+972)',
                r'יש את ([^.\n]{2,30}?)(?:\s*[.:,]|\s*$|\s+\d|\s*\+972)',
                r'([א-תA-Z][א-תA-Z\s]{1,20}?)(?:\s*[.:,]|\s*$|\s+\d|\s*\+972)',
            ]
            
            for pattern in name_patterns:
                name_match = re.search(pattern, before_phone, re.IGNORECASE)
                if name_match:
                    candidate = name_match.group(1).strip()
                    # Filter out common non-name words and validate it's a real name
                    # Exclude common Hebrew verbs/words that aren't names
                    excluded_words = ['תתקשר', 'יש', 'את', 'ל', 'מישהו', 'חברים', 'המלצה', 'פנו', 'ות']
                    if candidate and len(candidate) >= 2 and is_valid_name(candidate) and not any(word in candidate.lower() for word in excluded_words):
                        name = candidate
                        break
            
            # If no name found, check if there's a sentence mentioning the phone
            if not name:
                # Look for sentences containing the phone
                sentences = re.split(r'[.\n!?]', context)
                for sentence in sentences:
                    if phone in sentence:
                        # Extract potential name from sentence
                        words = sentence.split()
                        for word in words:
                            if word != phone and len(word) >= 2 and word[0].isalpha() and is_valid_name(word):
                                name = word
                                break
                        if name:
                            break
            
            # Intelligently extract service from context
            service = extract_service_from_context(text, chat_message_index=idx, all_messages=messages)
            if not service:
                service = extract_service_from_context(context, None, None)
            
            # Clean name (remove newlines, normalize whitespace)
            if name:
                name = name.replace('\n', ' ').strip()
                # Check if name contains service (e.g., "דויד - מתקין מזגנים")
                service_from_name = extract_service_from_name(name)
                if service_from_name and not service:
                    # Use service from name if we don't have one from context
                    service = service_from_name
                    # Clean the name (remove service part)
                    name_clean_patterns = [
                        r'^([^\-–—]+?)\s*[-–—]\s*.+$',  # Name - Service -> Name
                    ]
                    for pattern in name_clean_patterns:
                        match = re.match(pattern, name)
                        if match:
                            name = match.group(1).strip()
                            break
                # Validate name again after cleaning
                if not is_valid_name(name):
                    name = None
            
            if name or service:  # At least name or service to be a valid recommendation
                # Extract and normalize recommender phone number from sender
                recommender = extract_sender_phone(msg['sender'])
                
                recommendations.append({
                    'name': name or 'Unknown',
                    'phone': phone,
                    'service': service,
                    'date': msg['date'],
                    'recommender': recommender,  # Normalized phone number or sender as-is
                    'context': context.strip(),
                    'chat_message_index': idx  # Store chat message index for context lookup
                })
    
    return recommendations


def extract_vcf_mentions(messages: List[Dict], vcf_data: Dict) -> Tuple[List[Dict], set]:
    """Extract recommendations from .vcf file attachments mentioned in chat.
    
    Returns:
        Tuple of (recommendations list, mentioned_filenames set)
        The mentioned_filenames set includes ALL mentioned VCF files, even if they
        were skipped due to validation failures. This prevents data loss.
    """
    recommendations = []
    mentioned_filenames = set()  # Track ALL mentioned files, even if skipped
    
    for idx, msg in enumerate(messages):
        text = msg['text']
        
        # Look for .vcf file attachments
        vcf_pattern = r'([^.]+\.vcf)\s*\(file attached\)'
        vcf_matches = re.finditer(vcf_pattern, text, re.IGNORECASE)
        
        for match in vcf_matches:
            vcf_filename = match.group(1)
            vcf_key = vcf_filename.lower()
            
            if vcf_key in vcf_data:
                # Track as mentioned BEFORE validation (prevents data loss)
                mentioned_filenames.add(vcf_key)
                
                vcf_info = vcf_data[vcf_key]
                
                # Clean and validate name
                name = vcf_info['name']
                if name:
                    name = name.replace('\n', ' ').strip()
                    # Skip adding to recommendations if invalid, but still tracked as mentioned
                    if not is_valid_name(name):
                        continue
                
                # Get context (message and surrounding messages if available)
                context = msg['text']
                
                # Check for additional context in message (overrides filename extraction if better)
                service_from_context = extract_service_from_context(context, chat_message_index=idx, all_messages=messages)
                if service_from_context:
                    # Prefer context service if it exists, otherwise use filename service
                    vcf_info['service'] = service_from_context
                
                # Extract and normalize recommender phone number from sender
                recommender = extract_sender_phone(msg['sender'])
                
                recommendations.append({
                    'name': name,
                    'phone': vcf_info['phone'],
                    'service': vcf_info.get('service'),
                    'date': msg['date'],
                    'recommender': recommender,  # Normalized phone number or sender as-is
                    'context': context.strip(),
                    'chat_message_index': idx  # Store chat message index for context lookup
                })
    
    return recommendations, mentioned_filenames


def include_unmentioned_vcf_files(vcf_data: Dict, mentioned_filenames: set) -> List[Dict]:
    """Include .vcf files that were not mentioned in chat."""
    recommendations = []
    
    for vcf_key, vcf_info in vcf_data.items():
        if vcf_key not in mentioned_filenames:
            # Clean and validate name
            name = vcf_info['name']
            if name:
                name = name.replace('\n', ' ').strip()
                # Skip personal contacts
                if not is_valid_name(name):
                    continue
            
            recommendations.append({
                'name': name,
                'phone': vcf_info['phone'],
                'service': vcf_info.get('service'),
                'date': None,
                'recommender': None,
                'context': f"From file: {vcf_info['filename']}",
                'chat_message_index': None  # No chat message index for unmentioned VCF files
            })
    
    return recommendations


def extract_recommendations(
    project_root: Optional[Path] = None,
    run_analysis: bool = True
) -> List[Dict]:
    """Extract recommendations from WhatsApp chats and VCF files.
    
    Args:
        project_root: Project root directory (defaults to parent of src/)
        run_analysis: Whether to run analysis at the end (default: True)
    
    Returns:
        List of recommendation dictionaries
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent
    
    vcf_dir = project_root / 'data' / 'vcf'
    text_dir = project_root / 'data' / 'txt'
    output_file = project_root / 'web' / 'recommendations.json'
    backup_file = project_root / 'web' / 'recommendations_backup.json'
    
    print("Step 1: Parsing .vcf files...")
    vcf_data = parse_all_vcf_files(vcf_dir)
    print(f"  Found {len(vcf_data)} .vcf files")
    
    print("\nStep 2: Parsing WhatsApp chat files...")
    all_messages = parse_all_chat_files(text_dir)
    
    print("\nStep 3: Extracting text recommendations...")
    text_recs = extract_text_recommendations(all_messages, vcf_data)
    print(f"  Found {len(text_recs)} text recommendations")
    
    print("\nStep 4: Extracting .vcf mentions from chat...")
    vcf_mentions, mentioned_filenames = extract_vcf_mentions(all_messages, vcf_data)
    print(f"  Found {len(vcf_mentions)} .vcf file mentions")
    print(f"  Tracked {len(mentioned_filenames)} mentioned VCF files (including skipped invalid names)")
    
    print("\nStep 5: Including unmentioned .vcf files...")
    unmentioned_vcf = include_unmentioned_vcf_files(vcf_data, mentioned_filenames)
    print(f"  Found {len(unmentioned_vcf)} unmentioned .vcf files")
    
    print("\nStep 6: Merging all recommendations...")
    all_recommendations = text_recs + vcf_mentions + unmentioned_vcf
    
    # Remove duplicates (same name + phone, regardless of service)
    # Normalize phone numbers for comparison (remove +, spaces, dashes)
    import re as re_module
    
    seen = {}
    unique_recs = []
    duplicates_removed = 0
    
    for rec in all_recommendations:
        name = rec.get('name', '').strip()
        phone = rec.get('phone', '').strip()
        phone_normalized = re_module.sub(r'[\s+\-()]', '', phone)
        
        # Use name + normalized phone as key (service can vary for same person)
        key = (name.lower(), phone_normalized)
        
        if key in seen:
            # Check if this one has more information
            existing = seen[key]
            existing_score = (
                (1 if existing.get('service') else 0) +
                (1 if existing.get('context') and len(existing.get('context', '')) > 20 else 0) +
                (1 if existing.get('date') else 0)
            )
            new_score = (
                (1 if rec.get('service') else 0) +
                (1 if rec.get('context') and len(rec.get('context', '')) > 20 else 0) +
                (1 if rec.get('date') else 0)
            )
            
            if new_score > existing_score:
                # Replace with better one
                unique_recs.remove(existing)
                unique_recs.append(rec)
                seen[key] = rec
            duplicates_removed += 1
        else:
            seen[key] = rec
            unique_recs.append(rec)
    
    print(f"  Total unique recommendations: {len(unique_recs)}")
    
    # Save backup
    print(f"\nSaving backup to {backup_file}...")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(unique_recs, f, ensure_ascii=False, indent=2)
    
    print(f"\nWriting output to {output_file}...")
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_recs, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Generated {output_file} with {len(unique_recs)} recommendations.")
    
    # Analyze the output for potential issues (if requested)
    if run_analysis:
        print("\n" + "="*50)
        print("Analyzing recommendations for potential issues...")
        print("="*50)
        analyze_recommendations(output_file, verbose=True)
    
    return unique_recs


def main():
    """Main extraction function (CLI entry point)."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Extract recommendations from WhatsApp chats and VCF files')
    args = parser.parse_args()
    
    # Call the core extraction function
    extract_recommendations(run_analysis=True)


if __name__ == '__main__':
    main()


