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
    """Extract phone numbers from text (Israeli format)."""
    # Patterns for Israeli phone numbers
    patterns = [
        r'\+972[\s\-]?\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}',  # +972 format
        r'0\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}',  # 05X-XXX-XXXX format
        r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',  # XXX-XXX-XXXX (might be partial)
    ]
    
    phones = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            normalized = normalize_phone(match)
            # Only add if it looks like a valid phone number
            if len(re.sub(r'[^\d]', '', normalized)) >= 9:
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

