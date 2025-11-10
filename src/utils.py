#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for phone number handling and text processing.
"""

import re
from typing import List


def normalize_phone(phone_str: str) -> str:
    """Normalize phone number format."""
    # Remove all non-digit and non-+ characters except dashes
    phone = re.sub(r'[^\d+\-]', '', phone_str.strip())
    # Ensure consistent format
    if phone.startswith('+972'):
        phone = phone.replace(' ', '-')
    elif phone.startswith('0'):
        # Convert 05X-XXX-XXXX to +972 format
        if len(phone.replace('-', '')) == 10:
            phone = '+972-' + phone[1:4] + '-' + phone[4:]
    return phone


def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text (Israeli format), excluding URLs and IDs."""
    # First, identify and exclude URL contexts
    # URLs often contain numbers that look like phone numbers but aren't
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(com|net|org|co\.il|gov|io|app)[^\s]*'
    url_matches = []
    for match in re.finditer(url_pattern, text, re.IGNORECASE):
        url_matches.append((match.start(), match.end()))
    
    # Patterns for Israeli phone numbers
    patterns = [
        r'\+972[\s\-]?\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}',  # +972 format
        r'0\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}',  # 05X-XXX-XXXX format
        r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',  # XXX-XXX-XXXX (might be partial)
    ]
    
    phones = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            # Check if this match is inside a URL
            is_in_url = False
            match_start, match_end = match.span()
            for url_start, url_end in url_matches:
                if url_start <= match_start <= url_end or url_start <= match_end <= url_end:
                    is_in_url = True
                    break
            
            if is_in_url:
                continue
            
            # Also check if the phone is immediately preceded by URL-like characters
            before_phone = text[max(0, match_start - 10):match_start]
            if re.search(r'[\./=\?&#]', before_phone):
                # Likely part of a URL or parameter
                continue
            
            # Check if it's part of a social media ID pattern (e.g., /posts/1234567890)
            after_phone = text[match_end:min(len(text), match_end + 10)]
            if re.search(r'^[/\?&]', after_phone):
                # Likely part of a URL parameter
                continue
            
            normalized = normalize_phone(match.group())
            # Only add if it looks like a valid phone number (9-10 digits)
            digits_only = re.sub(r'[^\d]', '', normalized)
            if len(digits_only) >= 9 and len(digits_only) <= 10:
                # Additional validation: Israeli phone numbers should start with 0 or +972
                if normalized.startswith('0') or normalized.startswith('+972'):
                    phones.append(normalized)
    
    return list(set(phones))  # Remove duplicates


def format_phone(phone: str) -> str:
    """Format phone number for display."""
    if not phone:
        return ""
    # Clean up the phone number
    phone = str(phone).strip()
    
    # Handle +972 format
    if phone.startswith('+972'):
        phone = phone.replace('+972-', '').replace('+972', '').replace('-', '')
        if phone.startswith('0'):
            return phone[:3] + '-' + phone[3:6] + '-' + phone[6:]
        else:
            return '0' + phone[:2] + '-' + phone[2:5] + '-' + phone[5:]
    
    # Already in local format, ensure proper formatting
    phone = phone.replace(' ', '-').replace('(', '').replace(')', '')
    # If it doesn't have dashes and is 9-10 digits, add them
    digits_only = ''.join(c for c in phone if c.isdigit())
    if len(digits_only) == 9:
        return digits_only[:2] + '-' + digits_only[2:5] + '-' + digits_only[5:]
    elif len(digits_only) == 10:
        return digits_only[:3] + '-' + digits_only[3:6] + '-' + digits_only[6:]
    
    return phone

