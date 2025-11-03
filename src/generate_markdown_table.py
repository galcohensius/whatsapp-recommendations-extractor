#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a markdown table from recommendations.json
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import format_phone


def format_date(date: str) -> str:
    """Format date for display."""
    if not date:
        return ""
    # Extract just the date part if datetime
    return date.split()[0] if ' ' in date else date


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text and add ellipsis if too long."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    if not text:
        return ""
    # Escape pipe and other special chars for markdown tables
    return text.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def generate_markdown_table(recommendations: List[Dict], output_file: Path) -> None:
    """Generate a markdown table from recommendations."""
    
    # Group by service for better organization (optional - can be sorted differently)
    # For now, just sort by name
    
    # Sort recommendations: with service first, then by name
    sorted_recs = sorted(
        recommendations,
        key=lambda x: (
            x.get('service') is None,  # Items with service first
            x.get('service') or '',
            x.get('name', '').lower()
        )
    )
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Recommendations\n\n")
        f.write(f"Total recommendations: {len(recommendations)}\n\n")
        f.write("| Name | Phone | Service | Date | Recommender | Context |\n")
        f.write("|------|-------|---------|------|-------------|--------|\n")
        
        for rec in sorted_recs:
            name = escape_markdown(rec.get('name', 'Unknown'))
            phone = format_phone(rec.get('phone', ''))
            service = escape_markdown(rec.get('service') or '')
            date = format_date(rec.get('date', ''))
            recommender = escape_markdown(rec.get('recommender') or '')
            context = truncate_text(escape_markdown(rec.get('context', '')), 60)
            
            f.write(f"| {name} | {phone} | {service} | {date} | {recommender} | {context} |\n")
    
    print(f"Generated markdown table: {output_file}")
    print(f"Total recommendations: {len(recommendations)}")


def main():
    """Main function."""
    # Get project root (parent of src/)
    project_root = Path(__file__).parent.parent
    input_file = project_root / 'web' / 'recommendations.json'
    output_file = project_root / 'output' / 'recommendations.md'
    
    if not input_file.exists():
        print(f"Error: {input_file} not found!")
        return
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        recommendations = json.load(f)
    
    print(f"Found {len(recommendations)} recommendations")
    print(f"Generating markdown table...")
    
    generate_markdown_table(recommendations, output_file)
    
    print(f"Done! Output saved to {output_file}")


if __name__ == '__main__':
    main()

