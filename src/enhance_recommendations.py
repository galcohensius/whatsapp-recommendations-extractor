#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhance recommendations using OpenAI API to extract missing fields and improve existing data."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from openai import OpenAI


# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from extract_recommendations import get_full_context_for_recommendation


def build_enhancement_prompt(recommendations: List[Dict], messages: List[Dict], context_window: int = 5) -> str:
    """Build a comprehensive prompt for OpenAI to enhance all recommendations.
    
    Args:
        recommendations: List of recommendation dictionaries
        messages: List of all parsed messages for context lookup
        context_window: Number of messages before/after to include (default: 5)
    
    Returns:
        Formatted prompt string for OpenAI
    """
    prompt_parts = [
        "You are analyzing WhatsApp chat messages and contact files to extract and enhance business/service recommendations.",
        "",
        "For each recommendation below, I need you to:",
        "1. Extract missing fields (especially 'service' when null)",
        "2. Improve/correct existing fields (name, service, etc.)",
        "3. Preserve valid existing data",
        "4. All responses must be in valid JSON format",
        "",
        "IMPORTANT:",
        "- Return ALL recommendations in your response (even if unchanged)",
        "- Use the exact same structure as input",
        "- Keep phone numbers exactly as provided",
        "- Preserve dates, recommenders, and other metadata",
        "- Only enhance/improve fields, don't remove valid data",
        "",
        "RECOMMENDATIONS TO ENHANCE:",
        "="*80,
    ]
    
    # Add each recommendation with its full context
    for i, rec in enumerate(recommendations, 1):
        prompt_parts.append(f"\n--- Recommendation {i}/{len(recommendations)} ---")
        prompt_parts.append(f"Current data:")
        prompt_parts.append(f"  Name: {rec.get('name', 'Unknown')}")
        prompt_parts.append(f"  Phone: {rec.get('phone', 'N/A')}")
        prompt_parts.append(f"  Service: {rec.get('service', 'null')}")
        prompt_parts.append(f"  Date: {rec.get('date', 'N/A')}")
        prompt_parts.append(f"  Recommender: {rec.get('recommender', 'N/A')}")
        
        # Add full chat context
        full_context = get_full_context_for_recommendation(rec, messages, context_window=context_window)
        prompt_parts.append(f"\nFull chat context:")
        prompt_parts.append(full_context)
        prompt_parts.append("")
    
    prompt_parts.append("="*80)
    prompt_parts.append("")
    prompt_parts.append("Return a JSON object with this structure:")
    prompt_parts.append('{"recommendations": [/* array of enhanced recommendations */]}')
    prompt_parts.append("")
    prompt_parts.append("Each recommendation should have: name, phone, service, date, recommender, context, message_index")
    prompt_parts.append("Requirements:")
    prompt_parts.append("- Return ALL recommendations in the same order")
    prompt_parts.append("- Enhance missing services (especially when service is null)")
    prompt_parts.append("- Improve names if they are 'Unknown' or clearly wrong")
    prompt_parts.append("- Preserve all valid existing data (phone, date, recommender, message_index)")
    prompt_parts.append("- Keep phone numbers exactly as provided")
    prompt_parts.append("- Return service as null if truly not mentioned, otherwise extract it from context")
    
    return "\n".join(prompt_parts)


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count (1 token ≈ 4 characters for English/Hebrew)."""
    return len(text) // 4


def enhance_recommendations_with_openai(
    recommendations: List[Dict], 
    messages: List[Dict],
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    batch_size: int = 100  # Process 100 recommendations at a time
) -> Dict:
    """Enhance recommendations using OpenAI API with batch processing.
    
    Supported models:
    - gpt-5: Latest, best for coding/agentic tasks ($1.25/$10 per 1M tokens)
    - gpt-4.1: Smartest non-reasoning model ($2/$8 per 1M tokens)
    - o4-mini: Fast, cost-efficient reasoning ($1.10/$4.40 per 1M tokens)
    - gpt-4o-mini: Good balance (default, $0.15/$0.60 per 1M tokens)
    - gpt-4o: High quality ($2.50/$10 per 1M tokens)
    - gpt-3.5-turbo: Fastest, cheapest ($0.50/$1.50 per 1M tokens)
    
    Args:
        recommendations: List of recommendation dictionaries to enhance
        messages: List of all parsed messages for context lookup
        model: OpenAI model to use (default: gpt-4o-mini)
        api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
        batch_size: Number of recommendations to process per batch (default: 100)
    
    Returns:
        Dictionary with:
            - 'enhanced': List of enhanced recommendations
            - 'raw_response': Raw OpenAI response text
            - 'success': Boolean indicating if enhancement succeeded
            - 'error': Error message if failed
    """
    # Get API key
    if api_key is None:
        # Priority: 1) api_key.txt file, 2) environment variable, 3) other files
        project_root = Path(__file__).parent.parent
        api_key_file = project_root / 'api_key.txt'
        
        # First, try reading from api_key.txt (if it exists)
        if api_key_file.exists():
            try:
                api_key = api_key_file.read_text(encoding='utf-8').strip()
            except Exception:
                api_key = None
        
        # If not found in api_key.txt, try environment variable
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
        
        # If still not found, try other file locations
        if not api_key:
            key_files = [
                project_root / '.env',
                Path.home() / '.openai_key'
            ]
            
            for key_file in key_files:
                if key_file.exists():
                    try:
                        api_key = key_file.read_text(encoding='utf-8').strip()
                        # For .env files, look for OPENAI_API_KEY=... format
                        if key_file.name == '.env' and 'OPENAI_API_KEY=' in api_key:
                            api_key = api_key.split('OPENAI_API_KEY=', 1)[1].split('\n', 1)[0].strip().strip('"').strip("'")
                        if api_key:
                            break
                    except Exception:
                        continue
    
    if not api_key:
        return {
            'enhanced': recommendations,
            'raw_response': None,
            'success': False,
            'error': 'OPENAI_API_KEY not found. Set it as environment variable or in api_key.txt/.env file'
        }
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Model context limits (approximate)
        context_limits = {
            'gpt-4o-mini': 128000,
            'gpt-4o': 128000,
            'gpt-3.5-turbo': 16385,
            'gpt-5': 200000,  # Approximate
            'gpt-4.1': 128000,  # Approximate
            'o4-mini': 128000  # Approximate
        }
        
        max_tokens = context_limits.get(model, 128000)
        # Reserve tokens for response (estimate ~500 tokens per recommendation)
        safe_input_tokens = max_tokens - (batch_size * 500) - 1000  # Safety margin
        
        # Split into batches
        all_enhanced = []
        all_raw_responses = []
        total_batches = (len(recommendations) + batch_size - 1) // batch_size
        
        print(f"\nCalling OpenAI API ({model})...")
        print(f"  Total recommendations: {len(recommendations)}")
        print(f"  Processing in {total_batches} batches of ~{batch_size} recommendations each")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(recommendations))
            batch = recommendations[start_idx:end_idx]
            
            print(f"\n  Processing batch {batch_num + 1}/{total_batches} ({len(batch)} recommendations)...")
            
            # Build prompt for this batch (using context_window=5 for better understanding)
            prompt = build_enhancement_prompt(batch, messages, context_window=5)
            prompt_tokens = estimate_tokens(prompt)
            
            print(f"    Prompt: ~{prompt_tokens:,} tokens")
            
            # Check if prompt is too large
            if prompt_tokens > safe_input_tokens:
                print(f"    ⚠ Warning: Prompt size ({prompt_tokens:,} tokens) exceeds safe limit ({safe_input_tokens:,} tokens)")
                print(f"      Consider reducing batch_size if this causes errors")
            
            try:
                # Call OpenAI API with timeout
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that extracts and enhances business recommendations from chat messages. Always return valid JSON arrays."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    timeout=600.0  # 10 minute timeout per batch
                )
                
                raw_response = response.choices[0].message.content
                
                # Check if response content is None - handle gracefully
                if raw_response is None:
                    print(f"    ⚠ Batch {batch_num + 1} failed: OpenAI API returned empty response")
                    # Keep original recommendations for this batch
                    all_enhanced.extend(batch)
                    continue
                
                all_raw_responses.append(raw_response)
                
                # Parse JSON response
                response_data = json.loads(raw_response)
                
                # Extract recommendations array from response
                if isinstance(response_data, dict):
                    if 'recommendations' in response_data:
                        enhanced = response_data['recommendations']
                    elif 'enhanced' in response_data:
                        enhanced = response_data['enhanced']
                    elif 'data' in response_data:
                        enhanced = response_data['data']
                    else:
                        keys = [k for k in response_data.keys() if k.isdigit()]
                        if keys:
                            enhanced = [response_data[str(i)] for i in sorted([int(k) for k in keys])]
                        else:
                            raise ValueError("Could not find recommendations array in response")
                elif isinstance(response_data, list):
                    enhanced = response_data
                else:
                    raise ValueError("Unexpected response format")
                
                # Validate count
                if len(enhanced) != len(batch):
                    print(f"    ⚠ Warning: Expected {len(batch)} recommendations, got {len(enhanced)}")
                    # Merge with originals
                    enhanced = merge_enhancements(batch, enhanced)
                
                all_enhanced.extend(enhanced)
                print(f"    ✓ Batch {batch_num + 1} completed")
                
            except json.JSONDecodeError as e:
                print(f"    ⚠ Batch {batch_num + 1} failed: JSON parse error")
                print(f"      Error: {e}")
                # Keep original recommendations for this batch
                all_enhanced.extend(batch)
            except Exception as e:
                print(f"    ⚠ Batch {batch_num + 1} failed: {str(e)}")
                # Keep original recommendations for this batch
                all_enhanced.extend(batch)
        
        # Merge all results
        if len(all_enhanced) != len(recommendations):
            print(f"\n⚠ Warning: Total enhanced count ({len(all_enhanced)}) doesn't match original ({len(recommendations)})")
            # Fallback merge
            all_enhanced = merge_enhancements(recommendations, all_enhanced)
        
        return {
            'enhanced': all_enhanced,
            'raw_response': json.dumps(all_raw_responses, ensure_ascii=False, indent=2),  # Store all responses
            'success': True,
            'error': None
        }
        
    except Exception as e:
        return {
            'enhanced': recommendations,
            'raw_response': None,
            'success': False,
            'error': f'OpenAI API error: {str(e)}'
        }


def merge_enhancements(original: List[Dict], enhanced: List[Dict]) -> List[Dict]:
    """Merge OpenAI enhancements with original recommendations.
    
    Preserves original data and only updates fields that were enhanced.
    Matches by phone number and name (normalized).
    """
    merged = []
    
    for i, orig_rec in enumerate(original):
        # Try to find matching enhanced recommendation
        # First try by index (if order preserved), then by phone/name
        enhanced_rec = None
        
        if i < len(enhanced):
            enh = enhanced[i]
            # Verify it's the same recommendation
            if (enh.get('phone') == orig_rec.get('phone')):
                enhanced_rec = enh
        
        # If index match failed, search by phone
        if not enhanced_rec:
            for enh in enhanced:
                if enh.get('phone') == orig_rec.get('phone'):
                    enhanced_rec = enh
                    break
        
        if enhanced_rec:
            # Merge: use enhanced data but preserve original structure and metadata
            merged_rec = orig_rec.copy()
            
            # Always preserve: phone, date, recommender, message_index, context (original)
            # Update only: name, service
            
            # Update service if enhanced
            if enhanced_rec.get('service'):
                if not orig_rec.get('service'):
                    # Original was null, use enhanced
                    merged_rec['service'] = enhanced_rec['service']
                elif len(str(enhanced_rec.get('service'))) > len(str(orig_rec.get('service'))):
                    # Enhanced is more detailed, use it
                    merged_rec['service'] = enhanced_rec['service']
            
            # Improve name if enhanced is better
            enhanced_name = enhanced_rec.get('name')
            orig_name = orig_rec.get('name')
            if enhanced_name:
                if (orig_name == 'Unknown' and enhanced_name != 'Unknown'):
                    merged_rec['name'] = enhanced_name
                elif (orig_name and enhanced_name and 
                      len(enhanced_name) > len(orig_name)):
                    # Enhanced name is longer/more complete
                    merged_rec['name'] = enhanced_name
            
            merged.append(merged_rec)
        else:
            # No match found, keep original
            merged.append(orig_rec)
    
    return merged

