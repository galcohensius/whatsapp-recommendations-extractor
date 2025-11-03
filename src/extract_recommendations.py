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
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_phone, extract_phone_numbers
from analyze_recommendations import analyze_recommendations



def extract_service_from_filename(filename: str, name: Optional[str] = None) -> Optional[str]:
    """Intelligently extract service/category from filename.
    
    Removes the person's name from filename and returns any remaining meaningful text
    as the service description.
    """
    filename_stem = Path(filename).stem  # Remove .vcf extension
    
    # Remove the person's name from filename if provided
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


def parse_vcf_file(vcf_path: Path) -> Optional[Dict[str, Optional[str]]]:
    """Parse a .vcf file and extract name, phone, and infer service from filename."""
    try:
        with open(vcf_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract name from FN field
        name_match = re.search(r'FN:([^\r\n]+)', content)
        name = name_match.group(1).strip() if name_match else None
        
        # Extract phone from TEL fields (handle various formats)
        phone = None
        tel_patterns = [
            r'TEL[^:]*:([+\d\s\-]+)',
            r'item\d+\.TEL[^:]*:([+\d\s\-]+)',
        ]
        for pattern in tel_patterns:
            phone_match = re.search(pattern, content)
            if phone_match:
                phone = phone_match.group(1).strip()
                # Clean up phone number
                phone = re.sub(r'[^\d+\-]', '', phone)
                if phone.startswith('+972'):
                    # Normalize Israeli format
                    phone = phone.replace(' ', '-')
                break
        
        # Intelligently extract service from filename
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


def extract_service_from_context(text: str, message_index: Optional[int] = None, all_messages: Optional[List[Dict]] = None) -> Optional[str]:
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
    if all_messages and message_index is not None:
        # Look at current message and up to 2 previous messages
        for i in range(max(0, message_index - 2), message_index + 1):
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
        
        # Parse datetime
        try:
            datetime_obj = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            date_iso = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
        except:
            date_iso = None
        
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
        rec: Recommendation dictionary with 'message_index' field
        messages: List of all parsed messages
        context_window: Number of messages before and after to include (default: 5)
    
    Returns:
        Formatted string with full context, or original context if message_index is None
    """
    message_index = rec.get('message_index')
    
    # If no message index (e.g., unmentioned VCF files), return original context
    if message_index is None:
        return rec.get('context', '')
    
    # Ensure message_index is valid
    if message_index < 0 or message_index >= len(messages):
        return rec.get('context', '')
    
    # Get surrounding messages
    start_idx = max(0, message_index - context_window)
    end_idx = min(len(messages), message_index + context_window + 1)
    
    context_messages = []
    for i in range(start_idx, end_idx):
        msg = messages[i]
        date_str = msg.get('date', 'Unknown date')
        sender = msg.get('sender', 'Unknown sender')
        text = msg.get('text', '')
        
        # Mark the message that contains the recommendation
        marker = ">>> " if i == message_index else "    "
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
            service = extract_service_from_context(text, idx, messages)
            if not service:
                service = extract_service_from_context(context, None, None)
            
            # Clean name (remove newlines, normalize whitespace)
            if name:
                name = name.replace('\n', ' ').strip()
                # Validate name again after cleaning
                if not is_valid_name(name):
                    name = None
            
            if name or service:  # At least name or service to be a valid recommendation
                recommendations.append({
                    'name': name or 'Unknown',
                    'phone': phone,
                    'service': service,
                    'date': msg['date'],
                    'recommender': msg['sender'],
                    'context': context.strip(),
                    'message_index': idx  # Store message index for context lookup
                })
    
    return recommendations


def extract_vcf_mentions(messages: List[Dict], vcf_data: Dict) -> List[Dict]:
    """Extract recommendations from .vcf file attachments mentioned in chat."""
    recommendations = []
    
    for idx, msg in enumerate(messages):
        text = msg['text']
        
        # Look for .vcf file attachments
        vcf_pattern = r'([^.]+\.vcf)\s*\(file attached\)'
        vcf_matches = re.finditer(vcf_pattern, text, re.IGNORECASE)
        
        for match in vcf_matches:
            vcf_filename = match.group(1)
            vcf_key = vcf_filename.lower()
            
            if vcf_key in vcf_data:
                vcf_info = vcf_data[vcf_key]
                
                # Clean and validate name
                name = vcf_info['name']
                if name:
                    name = name.replace('\n', ' ').strip()
                    # Skip personal contacts
                    if not is_valid_name(name):
                        continue
                
                # Get context (message and surrounding messages if available)
                context = msg['text']
                
                # Check for additional context in message (overrides filename extraction if better)
                service_from_context = extract_service_from_context(context, idx, messages)
                if service_from_context:
                    # Prefer context service if it exists, otherwise use filename service
                    vcf_info['service'] = service_from_context
                
                recommendations.append({
                    'name': name,
                    'phone': vcf_info['phone'],
                    'service': vcf_info.get('service'),
                    'date': msg['date'],
                    'recommender': msg['sender'],
                    'context': context.strip(),
                    'message_index': idx  # Store message index for context lookup
                })
    
    return recommendations


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
                'message_index': None  # No message index for unmentioned VCF files
            })
    
    return recommendations


def main():
    """Main extraction function."""
    # Get project root (parent of src/)
    project_root = Path(__file__).parent.parent
    vcf_dir = project_root / 'data' / 'vcf'
    text_dir = project_root / 'data' / 'txt'  # Using 'txt' since that's where your file is
    output_file = project_root / 'web' / 'recommendations.json'
    
    print("Step 1: Parsing .vcf files...")
    vcf_data = parse_all_vcf_files(vcf_dir)
    print(f"  Found {len(vcf_data)} .vcf files")
    
    print("\nStep 2: Parsing WhatsApp chat files...")
    all_messages = parse_all_chat_files(text_dir)
    
    print("\nStep 3: Extracting text recommendations...")
    text_recs = extract_text_recommendations(all_messages, vcf_data)
    print(f"  Found {len(text_recs)} text recommendations")
    
    print("\nStep 4: Extracting .vcf mentions from chat...")
    vcf_mentions = extract_vcf_mentions(all_messages, vcf_data)
    print(f"  Found {len(vcf_mentions)} .vcf file mentions")
    
    # Track which .vcf files were mentioned
    mentioned_filenames = set()
    for rec in vcf_mentions:
        # Find the vcf file that matches
        for vcf_key, vcf_info in vcf_data.items():
            if vcf_info['name'] == rec['name'] and vcf_info['phone'] == rec['phone']:
                mentioned_filenames.add(vcf_key)
                break
    
    print("\nStep 5: Including unmentioned .vcf files...")
    unmentioned_vcf = include_unmentioned_vcf_files(vcf_data, mentioned_filenames)
    print(f"  Found {len(unmentioned_vcf)} unmentioned .vcf files")
    
    print("\nStep 6: Merging all recommendations...")
    all_recommendations = text_recs + vcf_mentions + unmentioned_vcf
    
    # Remove exact duplicates (same name, phone, service)
    seen = set()
    unique_recs = []
    for rec in all_recommendations:
        key = (rec['name'], rec['phone'], rec.get('service'))
        if key not in seen:
            seen.add(key)
            unique_recs.append(rec)
        else:
            # If duplicate but has more context, prefer the one with more info
            existing = next(r for r in unique_recs if (r['name'], r['phone'], r.get('service')) == key)
            if rec.get('context') and (not existing.get('context') or len(rec['context']) > len(existing.get('context', ''))):
                unique_recs.remove(existing)
                unique_recs.append(rec)
                continue
    
    print(f"  Total unique recommendations: {len(unique_recs)}")
    
    print(f"\nWriting output to {output_file}...")
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_recs, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Generated {output_file} with {len(unique_recs)} recommendations.")
    
    # Analyze the output for potential issues
    print("\n" + "="*50)
    print("Analyzing recommendations for potential issues...")
    print("="*50)
    analyze_recommendations(output_file, verbose=True)


if __name__ == '__main__':
    main()


