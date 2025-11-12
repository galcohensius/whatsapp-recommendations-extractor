#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhance recommendations using OpenAI API to extract missing fields and improve existing data."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from openai import OpenAI


# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from extract_txt_and_vcf import get_full_context_for_recommendation


def build_enhancement_prompt_for_null_services(recommendations: List[Dict], messages: List[Dict], context_window: int = 10) -> str:
    """Build a focused prompt for OpenAI to extract services for recommendations with null service.
    
    Args:
        recommendations: List of recommendation dictionaries with service=None
        messages: List of all parsed messages for context lookup
        context_window: Number of messages before/after to include (default: 10 for extended context)
    
    Returns:
        Formatted prompt string for OpenAI
    """
    prompt_parts = [
        "You are analyzing WhatsApp chat messages to extract OCCUPATIONS/SERVICES for recommendations.",
        "",
        "CRITICAL: The 'service' field is the MOST IMPORTANT field. If service cannot be extracted, the entry should be removed.",
        "",
        "For each recommendation below that has service=null, extract the OCCUPATION from the chat context.",
        "The 'service' field should contain ONLY the person's OCCUPATION/SERVICE NAME - NOT full sentences or conversational text.",
        "",
        "EXAMPLES of CORRECT service extraction:",
        "  - 'מוביל' (NOT 'לכם המלצה על מוביל טוב')",
        "  - 'חשמלאי' (NOT 'המלצה על חשמלאי מעולה')",
        "  - 'מתקין מזגנים' (NOT 'מומלץ מתקין מזגנים')",
        "  - 'אינסטלטור' (NOT 'יש לכם המלצה על אינסטלטור?')",
        "",
        "The 'service' field should contain the person's OCCUPATION (e.g., 'מתקין מזגנים', 'חשמלאי', 'אינסטלטור', 'רופא', 'טכנאי מחשבים', 'מוביל', 'גנן').",
        "Any other important information (quality of work, location hints, pricing, etc.) should be placed in the 'context' field.",
        "For the 'recommender' field: Keep it as the phone number only. Do NOT add names. The recommender is the SENDER of the message (their phone number is already in the field).",
        "  Keep the recommender field as just the phone number - do NOT format as 'Name - Phone'.",
        "",
        "IMPORTANT:",
        "- Return ALL recommendations in your response (even if unchanged)",
        "- Only update the 'service' field (with OCCUPATION) for recommendations where service is null",
        "- Extract ONLY the service/occupation name - remove all conversational prefixes like 'לכם המלצה על', 'מומלץ', etc.",
        "- Update the 'context' field with any additional relevant information from the chat (work quality, location, pricing, etc.)",
        "- For the 'recommender' field: Keep it as the phone number only. Do NOT add names or format as 'Name - Phone'.",
        "- Use the exact same structure as input",
        "- Keep all other fields (name, phone, date, chat_message_index) exactly as provided",
        "- If you cannot determine an occupation from context, leave service as null (entry will be removed)",
        "",
        "RECOMMENDATIONS TO ENHANCE (service=null):",
        "="*80,
    ]
    
    # Add each recommendation with extended context
    for i, rec in enumerate(recommendations, 1):
        prompt_parts.append(f"\n--- Recommendation {i}/{len(recommendations)} ---")
        prompt_parts.append(f"Current data:")
        prompt_parts.append(f"  Name: {rec.get('name', 'Unknown')}")
        prompt_parts.append(f"  Phone: {rec.get('phone', 'N/A')}")
        prompt_parts.append(f"  Service: null (NEEDS EXTRACTION)")
        prompt_parts.append(f"  Date: {rec.get('date', 'N/A')}")
        prompt_parts.append(f"  Recommender: {rec.get('recommender', 'N/A')}")
        
        # Add extended chat context (±10 messages)
        full_context = get_full_context_for_recommendation(rec, messages, context_window=context_window)
        prompt_parts.append(f"\nExtended chat context (±{context_window} messages):")
        prompt_parts.append(full_context)
        prompt_parts.append("")
    
    prompt_parts.append("="*80)
    prompt_parts.append("")
    prompt_parts.append("Return a JSON object with this structure:")
    prompt_parts.append('{"recommendations": [/* array of recommendations with extracted services */]}')
    prompt_parts.append("")
    prompt_parts.append("Requirements:")
    prompt_parts.append("- Return ALL recommendations in the same order")
    prompt_parts.append("- ONLY update the 'service' field (with OCCUPATION) for entries where service was null")
    prompt_parts.append("- Extract ONLY the OCCUPATION/SERVICE NAME from the extended context - NOT full sentences")
    prompt_parts.append("  Examples: 'מוביל', 'חשמלאי', 'מתקין מזגנים', 'אינסטלטור', 'רופא', 'טכנאי מחשבים', 'גנן', 'מתווך'")
    prompt_parts.append("  Remove conversational prefixes like 'לכם המלצה על', 'מומלץ', 'המלצה על' - extract just the service name")
    prompt_parts.append("- Update 'context' field with additional relevant information (work quality, location, pricing, specializations, etc.)")
    prompt_parts.append("- For the 'recommender' field: Keep it as the phone number only. Do NOT add names or format as 'Name - Phone'.")
    prompt_parts.append("  The recommender is the SENDER of the message (their phone number is already in the field).")
    prompt_parts.append("- Keep all other fields exactly as provided")
    prompt_parts.append("- If occupation cannot be determined, leave service as null (entry will be removed)")
    
    return "\n".join(prompt_parts)


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
        "You are analyzing WhatsApp chat messages and contact files to extract and enhance business recommendations.",
        "",
        "CRITICAL: The 'service' field is the MOST IMPORTANT field. Extract ONLY the service/occupation name - NOT full sentences.",
        "",
        "For each recommendation below, I need you to:",
        "1. Extract OCCUPATION in the 'service' field ONLY when service is null (do NOT change existing service values)",
        "2. The 'service' field should contain ONLY the person's OCCUPATION/SERVICE NAME - NOT full sentences or conversational text.",
        "",
        "EXAMPLES of CORRECT service extraction:",
        "  - 'מוביל' (NOT 'לכם המלצה על מוביל טוב')",
        "  - 'חשמלאי' (NOT 'המלצה על חשמלאי מעולה')",
        "  - 'מתקין מזגנים' (NOT 'מומלץ מתקין מזגנים')",
        "",
        "3. For ALL entries (regardless of service value): Place other important information in the 'context' field (work quality, location, pricing, specializations, experience level, etc.)",
        "4. For ALL entries (regardless of service value): Keep the 'recommender' field as the phone number only. Do NOT add names or format as 'Name - Phone'. The recommender is the SENDER of the message (their phone number is already in the field).",
        "5. Improve/correct existing fields (name, context, recommender) - but do NOT change existing service values",
        "6. Preserve valid existing data (especially existing service values)",
        "7. All responses must be in valid JSON format",
        "",
        "IMPORTANT:",
        "- Return ALL recommendations in your response (even if unchanged)",
        "- Use the exact same structure as input",
        "- Keep phone numbers exactly as provided",
        "- Preserve dates and other metadata",
        "- For ALL entries: Keep 'recommender' field as phone number only. Do NOT add names.",
        "- For ALL entries: Update 'context' field with additional relevant information",
        "- Only update 'service' field when it is null (do NOT change existing service values)",
        "- When extracting service, extract ONLY the service/occupation name - remove conversational prefixes like 'לכם המלצה על', 'מומלץ', etc.",
        "- Only enhance/improve fields, don't remove valid data",
        "- 'service' = OCCUPATION only; other details go in 'context'",
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
    prompt_parts.append("Each recommendation should have: name, phone, service, date, recommender, context, chat_message_index")
    prompt_parts.append("Requirements:")
    prompt_parts.append("- Return ALL recommendations in the same order")
    prompt_parts.append("- Extract OCCUPATION in 'service' field ONLY when service is null (do NOT update existing service values)")
    prompt_parts.append("- 'service' should contain ONLY the occupation/service name - NOT full sentences")
    prompt_parts.append("  Examples: 'מוביל', 'חשמלאי', 'מתקין מזגנים', 'רופא' - remove prefixes like 'לכם המלצה על', 'מומלץ', etc.")
    prompt_parts.append("- For ALL entries (regardless of service value): Update 'context' field with additional relevant information (work quality, location, pricing, specializations, experience, etc.)")
    prompt_parts.append("- For ALL entries (regardless of service value): Keep 'recommender' field as phone number only. Do NOT add names or format as 'Name - Phone'.")
    prompt_parts.append("  The recommender is the SENDER of the message (their phone number is already in the field).")
    prompt_parts.append("- Improve names if they are 'Unknown' or clearly wrong")
    prompt_parts.append("- Preserve all valid existing data (phone, date, chat_message_index)")
    prompt_parts.append("- Keep phone numbers exactly as provided")
    prompt_parts.append("- Return service as null if occupation cannot be determined, otherwise extract it from context ONLY when service was originally null")
    
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
            
            # Use smart context windows: extended (10) for null services, normal (5) for others
            # Build prompt with per-recommendation context windows
            # Split batch into null-service and non-null-service groups for different context windows
            null_service_batch = [rec for rec in batch if not rec.get('service')]
            non_null_service_batch = [rec for rec in batch if rec.get('service')]
            
            all_enhanced_batch = []
            
            # Process null service entries with extended context (context_window=10)
            if null_service_batch:
                print(f"    Processing {len(null_service_batch)} entries with null service (extended context)...")
                prompt = build_enhancement_prompt(null_service_batch, messages, context_window=10)
                prompt_tokens = estimate_tokens(prompt)
                
                print(f"      Prompt: ~{prompt_tokens:,} tokens")
                
                # Check if prompt is too large
                if prompt_tokens > safe_input_tokens:
                    print(f"      ⚠ Warning: Prompt size ({prompt_tokens:,} tokens) exceeds safe limit ({safe_input_tokens:,} tokens)")
                    print(f"        Consider reducing batch_size if this causes errors")
                
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that extracts and enhances business recommendations from chat messages. CRITICAL: The 'service' field is the MOST IMPORTANT field. Extract ONLY the service/occupation name (e.g., 'מוביל', 'חשמלאי') - NOT full sentences like 'לכם המלצה על מוביל טוב'. Remove conversational prefixes. IMPORTANT: Only update the 'service' field when it is null - do NOT change existing service values. For ALL entries (regardless of service value), update the 'context' field with additional relevant information. For the 'recommender' field: Keep it as the phone number only. Do NOT add names or format as 'Name - Phone'. The recommender is the SENDER of the message (their phone number is already in the field). Always return valid JSON arrays."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                        timeout=600.0
                    )
                    
                    raw_response = response.choices[0].message.content
                    
                    if raw_response is None:
                        print(f"      ⚠ Null service batch failed: OpenAI API returned empty response")
                        all_enhanced_batch.extend(null_service_batch)
                    else:
                        all_raw_responses.append(raw_response)
                        response_data = json.loads(raw_response)
                        
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
                        
                        enhanced = merge_enhancements(null_service_batch, enhanced)
                        all_enhanced_batch.extend(enhanced)
                        print(f"      ✓ Null service entries processed")
                        
                except Exception as e:
                    print(f"      ⚠ Null service batch failed: {str(e)}")
                    all_enhanced_batch.extend(null_service_batch)
            
            # Process non-null service entries with normal context (context_window=5)
            if non_null_service_batch:
                print(f"    Processing {len(non_null_service_batch)} entries with existing service (normal context)...")
                prompt = build_enhancement_prompt(non_null_service_batch, messages, context_window=5)
                prompt_tokens = estimate_tokens(prompt)
            
                print(f"      Prompt: ~{prompt_tokens:,} tokens")
                
                if prompt_tokens > safe_input_tokens:
                    print(f"      ⚠ Warning: Prompt size ({prompt_tokens:,} tokens) exceeds safe limit ({safe_input_tokens:,} tokens)")
                    print(f"        Consider reducing batch_size if this causes errors")
                
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that extracts and enhances business recommendations from chat messages. CRITICAL: The 'service' field is the MOST IMPORTANT field. Extract ONLY the service/occupation name (e.g., 'מוביל', 'חשמלאי') - NOT full sentences like 'לכם המלצה על מוביל טוב'. Remove conversational prefixes. IMPORTANT: Only update the 'service' field when it is null - do NOT change existing service values. For ALL entries (regardless of service value), update the 'context' field with additional relevant information. For the 'recommender' field: Keep it as the phone number only. Do NOT add names or format as 'Name - Phone'. The recommender is the SENDER of the message (their phone number is already in the field). Always return valid JSON arrays."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                        timeout=600.0
                    )
                    
                    raw_response = response.choices[0].message.content
                    
                    if raw_response is None:
                        print(f"      ⚠ Non-null service batch failed: OpenAI API returned empty response")
                        all_enhanced_batch.extend(non_null_service_batch)
                    else:
                        all_raw_responses.append(raw_response)
                        response_data = json.loads(raw_response)
                        
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
                        
                        enhanced = merge_enhancements(non_null_service_batch, enhanced)
                        all_enhanced_batch.extend(enhanced)
                        print(f"      ✓ Non-null service entries processed")
                        
                except Exception as e:
                    print(f"      ⚠ Non-null service batch failed: {str(e)}")
                    all_enhanced_batch.extend(non_null_service_batch)
            
            # Combine both groups (maintain original order)
            # Reconstruct batch in original order
            enhanced_dict = {rec.get('phone'): rec for rec in all_enhanced_batch}
            final_batch = []
            for rec in batch:
                phone = rec.get('phone')
                if phone in enhanced_dict:
                    final_batch.append(enhanced_dict[phone])
                else:
                    final_batch.append(rec)
            
            all_enhanced.extend(final_batch)
            print(f"    ✓ Batch {batch_num + 1} completed")
        
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


def enhance_null_services_with_openai(
    recommendations: List[Dict], 
    messages: List[Dict],
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    batch_size: int = 50,  # Smaller batches for extended context
    context_window: int = 10  # Number of messages before/after to include
) -> Dict:
    """Second pass: Enhance only recommendations with service=null using extended context.
    
    Args:
        recommendations: List of recommendation dictionaries (only those with service=None will be processed)
        messages: List of all parsed messages for context lookup
        model: OpenAI model to use (default: gpt-4o-mini)
        api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
        batch_size: Number of recommendations to process per batch (default: 50, smaller due to extended context)
        context_window: Number of messages before/after to include (default: 10, can be increased to 20 for more context)
    
    Returns:
        Dictionary with:
            - 'enhanced': List of recommendations with extracted services (only service field updated)
            - 'raw_response': Raw OpenAI response text
            - 'success': Boolean indicating if enhancement succeeded
            - 'error': Error message if failed
    """
    # Filter to only null services
    null_service_recs = [rec for rec in recommendations if not rec.get('service')]
    
    if not null_service_recs:
        print("\n  No recommendations with null service found. Skipping second pass.")
        return {
            'enhanced': recommendations,
            'raw_response': None,
            'success': True,
            'error': None
        }
    
    print(f"\n  Second pass: Extracting services for {len(null_service_recs)} recommendations with null service...")
    print(f"    Using extended context (±{context_window} messages per recommendation)")
    
    # Get API key (same logic as main enhancement function)
    if api_key is None:
        project_root = Path(__file__).parent.parent
        api_key_file = project_root / 'api_key.txt'
        
        if api_key_file.exists():
            try:
                api_key = api_key_file.read_text(encoding='utf-8').strip()
            except Exception:
                api_key = None
        
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            key_files = [
                project_root / '.env',
                Path.home() / '.openai_key'
            ]
            
            for key_file in key_files:
                if key_file.exists():
                    try:
                        api_key = key_file.read_text(encoding='utf-8').strip()
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
            'gpt-5': 200000,
            'gpt-4.1': 128000,
            'o4-mini': 128000
        }
        
        max_tokens = context_limits.get(model, 128000)
        # Reserve tokens for response (estimate ~300 tokens per recommendation for extended context)
        safe_input_tokens = max_tokens - (batch_size * 300) - 1000  # Safety margin
        
        # Split into batches
        all_enhanced_null = []
        all_raw_responses = []
        total_batches = (len(null_service_recs) + batch_size - 1) // batch_size
        
        print(f"    Processing {len(null_service_recs)} recommendations in {total_batches} batches...")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(null_service_recs))
            batch = null_service_recs[start_idx:end_idx]
            
            print(f"      Batch {batch_num + 1}/{total_batches} ({len(batch)} recommendations)...")
            
            # Build prompt with extended context
            prompt = build_enhancement_prompt_for_null_services(batch, messages, context_window=context_window)
            prompt_tokens = estimate_tokens(prompt)
            
            print(f"        Prompt: ~{prompt_tokens:,} tokens")
            
            if prompt_tokens > safe_input_tokens:
                print(f"        ⚠ Warning: Prompt size ({prompt_tokens:,} tokens) exceeds safe limit ({safe_input_tokens:,} tokens)")
            
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that extracts OCCUPATIONS from chat messages. The 'service' field should contain the person's OCCUPATION. Other relevant details should go in the 'context' field. For the 'recommender' field: Keep it as the phone number only. Do NOT add names or format as 'Name - Phone'. The recommender is the SENDER of the message (their phone number is already in the field). Always return valid JSON arrays. Only update the 'service', 'context', and 'recommender' fields for entries where service is null."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    timeout=600.0
                )
                
                raw_response = response.choices[0].message.content
                
                if raw_response is None:
                    print(f"        ⚠ Batch {batch_num + 1} failed: OpenAI API returned empty response")
                    all_enhanced_null.extend(batch)
                    continue
                
                all_raw_responses.append(raw_response)
                
                # Parse JSON response
                response_data = json.loads(raw_response)
                
                # Extract recommendations array
                if isinstance(response_data, dict):
                    if 'recommendations' in response_data:
                        enhanced = response_data['recommendations']
                    elif 'enhanced' in response_data:
                        enhanced = response_data['enhanced']
                    else:
                        enhanced = list(response_data.values()) if response_data else []
                elif isinstance(response_data, list):
                    enhanced = response_data
                else:
                    enhanced = []
                
                # Always merge to preserve original fields (chat_message_index, date, phone, etc.)
                # Merge: update service (occupation), context, and recommender fields, keep all else
                # Validate count
                if len(enhanced) != len(batch):
                    print(f"        ⚠ Warning: Expected {len(batch)} recommendations, got {len(enhanced)}")
                    print(f"          This may result in some recommendations not being enhanced. OpenAI may have filtered some items.")
                
                # Use merge_enhancements to properly match and merge (handles count mismatches better)
                # This ensures all items in batch are preserved, even if OpenAI returns fewer items
                merged_batch = merge_enhancements(batch, enhanced)
                
                # Add all merged items (merge_enhancements preserves all originals and merges enhancements)
                for orig_rec in merged_batch:
                    all_enhanced_null.append(orig_rec)
                
                print(f"        ✓ Batch {batch_num + 1} completed")
                
            except json.JSONDecodeError as e:
                print(f"        ⚠ Batch {batch_num + 1} failed: JSON parse error")
                all_enhanced_null.extend(batch)
            except Exception as e:
                print(f"        ⚠ Batch {batch_num + 1} failed: {str(e)}")
                all_enhanced_null.extend(batch)
        
        # Merge back into original recommendations list
        # Helper function to normalize phone for matching
        def normalize_phone(phone):
            """Normalize phone number for matching (remove formatting)"""
            if not phone:
                return ''
            # Remove all non-digit characters except +
            normalized = re.sub(r'[^\d+]', '', str(phone))
            # Remove leading +972 and replace with 0
            if normalized.startswith('+972'):
                normalized = '0' + normalized[4:]
            elif normalized.startswith('972'):
                normalized = '0' + normalized[3:]
            return normalized
        
        # Helper function to normalize name for matching
        def normalize_name(name):
            """Normalize name for matching"""
            if not name:
                return ''
            return str(name).strip().lower()
        
        # Create a map of null service recs by normalized phone+name for quick lookup
        null_service_map = {}
        null_service_map_by_phone = {}  # Fallback: match by phone only
        
        for rec in all_enhanced_null:
            phone = normalize_phone(rec.get('phone', ''))
            name = normalize_name(rec.get('name', ''))
            key = (phone, name)
            null_service_map[key] = rec
            # Also index by phone only for fallback matching
            if phone:
                if phone not in null_service_map_by_phone:
                    null_service_map_by_phone[phone] = []
                null_service_map_by_phone[phone].append(rec)
        
        # Helper function for case-insensitive field lookup
        def get_field(rec, field_name):
            """Get field value with case-insensitive lookup"""
            if field_name in rec:
                val = rec[field_name]
                if val and val != 'None' and val != 'null':
                    return val
            capitalized = field_name.capitalize()
            if capitalized in rec:
                val = rec[capitalized]
                if val and val != 'None' and val != 'null':
                    return val
            variations = {
                'name': ['Name', 'NAME'],
                'phone': ['Phone', 'PHONE'],
                'service': ['Service', 'SERVICE'],
                'recommender': ['Recommender', 'RECOMMENDER'],
                'context': ['Context', 'CONTEXT'],
                'date': ['Date', 'DATE']
            }
            if field_name.lower() in variations:
                for var in variations[field_name.lower()]:
                    if var in rec:
                        val = rec[var]
                        if val and val != 'None' and val != 'null':
                            return val
            return None
        
        # Count null services before update
        null_before = sum(1 for r in recommendations if not r.get('service'))
        
        # Track matching statistics
        matched_exact = 0
        matched_by_phone = 0
        unmatched = 0
        
        # Update original recommendations
        updated_recommendations = []
        for rec in recommendations:
            if not rec.get('service'):
                phone = normalize_phone(rec.get('phone', ''))
                name = normalize_name(rec.get('name', ''))
                key = (phone, name)
                enhanced_rec = None
                match_type = None
                
                # Try exact match first
                if key in null_service_map:
                    enhanced_rec = null_service_map[key]
                    match_type = 'exact'
                    matched_exact += 1
                # Fallback: match by phone only (if only one candidate)
                elif phone and phone in null_service_map_by_phone:
                    candidates = null_service_map_by_phone[phone]
                    if len(candidates) == 1:
                        enhanced_rec = candidates[0]
                        match_type = 'phone_only'
                        matched_by_phone += 1
                
                if enhanced_rec:
                    # Update service (occupation) from enhanced version using case-insensitive lookup
                    service = get_field(enhanced_rec, 'service')
                    if service:
                        rec['service'] = service
                    # Update context with additional information
                    enhanced_context = get_field(enhanced_rec, 'context') or enhanced_rec.get('context', '')
                    orig_context = rec.get('context', '')
                    if enhanced_context and enhanced_context != orig_context:
                        if orig_context and orig_context.strip():
                            # Combine contexts, avoiding duplicates
                            if enhanced_context not in orig_context:
                                rec['context'] = f"{orig_context}. {enhanced_context}".strip()
                            # else keep original if enhanced is subset
                        else:
                            # No original context, use enhanced
                            rec['context'] = enhanced_context
                    # Keep recommender as phone number only - do NOT add names
                    # If enhanced version has "Name - Phone" format, extract just the phone part
                    enhanced_recommender = get_field(enhanced_rec, 'recommender') or enhanced_rec.get('recommender', '')
                    orig_recommender = rec.get('recommender', '')
                    if enhanced_recommender and enhanced_recommender != orig_recommender:
                        # If enhanced has "Name - Phone" format, extract just the phone part
                        if ' - ' in enhanced_recommender:
                            parts = enhanced_recommender.split(' - ', 1)
                            if len(parts) == 2:
                                phone_part = parts[1].strip()
                                # Use just the phone number, not the name
                                rec['recommender'] = phone_part
                        elif not orig_recommender or orig_recommender == 'Unknown':
                            # No original recommender, use enhanced (but only if it's a phone number, not a name)
                            # Check if it looks like a phone number (contains digits)
                            if re.search(r'\d', enhanced_recommender):
                                rec['recommender'] = enhanced_recommender
                else:
                    # No match found - this recommendation was likely filtered by OpenAI
                    unmatched += 1
            updated_recommendations.append(rec)
        
        # Count null services after update
        null_after = sum(1 for r in updated_recommendations if not r.get('service'))
        extracted_count = null_before - null_after
        
        # Enhanced logging
        print(f"    ✓ Matching statistics:")
        print(f"      - Exact matches (phone+name): {matched_exact}")
        print(f"      - Phone-only matches: {matched_by_phone}")
        print(f"      - Unmatched (filtered by OpenAI): {unmatched}")
        print(f"    ✓ Extracted services for {extracted_count} recommendations")
        if unmatched > 0:
            print(f"    ⚠ Warning: {unmatched} recommendations were not matched (likely filtered by OpenAI)")
        
        return {
            'enhanced': updated_recommendations,
            'raw_response': json.dumps(all_raw_responses, ensure_ascii=False, indent=2),
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
            
            # Helper function for case-insensitive field lookup
            def get_field(rec, field_name):
                """Get field value with case-insensitive lookup"""
                if field_name in rec:
                    val = rec[field_name]
                    if val and val != 'None' and val != 'null':
                        return val
                capitalized = field_name.capitalize()
                if capitalized in rec:
                    val = rec[capitalized]
                    if val and val != 'None' and val != 'null':
                        return val
                variations = {
                    'name': ['Name', 'NAME'],
                    'phone': ['Phone', 'PHONE'],
                    'service': ['Service', 'SERVICE'],
                    'recommender': ['Recommender', 'RECOMMENDER'],
                    'context': ['Context', 'CONTEXT'],
                    'date': ['Date', 'DATE']
                }
                if field_name.lower() in variations:
                    for var in variations[field_name.lower()]:
                        if var in rec:
                            val = rec[var]
                            if val and val != 'None' and val != 'null':
                                return val
                return None
            
            # Always preserve: phone, date, chat_message_index, service (if already exists)
            # Update: name, service (only if null), context (additional info), recommender (add name if available)
            
            # Update service (occupation) ONLY if original was null
            service = get_field(enhanced_rec, 'service')
            if service:
                if not orig_rec.get('service'):
                    # Original was null, use enhanced
                    merged_rec['service'] = service
                # Do NOT update service if it already exists (preserve existing value)
            
            # Improve name if enhanced is better
            enhanced_name = get_field(enhanced_rec, 'name') or enhanced_rec.get('name')
            orig_name = orig_rec.get('name')
            if enhanced_name:
                if (orig_name == 'Unknown' and enhanced_name != 'Unknown'):
                    merged_rec['name'] = enhanced_name
                elif (orig_name and enhanced_name and 
                      len(enhanced_name) > len(orig_name)):
                    # Enhanced name is longer/more complete
                    merged_rec['name'] = enhanced_name
            
            # Update context with additional information from enhanced version
            enhanced_context = get_field(enhanced_rec, 'context') or enhanced_rec.get('context', '')
            orig_context = orig_rec.get('context', '')
            if enhanced_context and enhanced_context != orig_context:
                # Merge context: combine if both exist, or use enhanced if it's more detailed
                if orig_context and orig_context.strip():
                    # Combine contexts, avoiding duplicates
                    if enhanced_context not in orig_context:
                        merged_rec['context'] = f"{orig_context}. {enhanced_context}".strip()
                    else:
                        merged_rec['context'] = orig_context  # Keep original if enhanced is subset
                else:
                    # No original context, use enhanced
                    merged_rec['context'] = enhanced_context
            
            # Keep recommender as phone number only - do NOT add names
            # If enhanced version has "Name - Phone" format, extract just the phone part
            enhanced_recommender = get_field(enhanced_rec, 'recommender') or enhanced_rec.get('recommender', '')
            orig_recommender = orig_rec.get('recommender', '')
            if enhanced_recommender and enhanced_recommender != orig_recommender:
                # If enhanced has "Name - Phone" format, extract just the phone part
                if ' - ' in enhanced_recommender:
                    parts = enhanced_recommender.split(' - ', 1)
                    if len(parts) == 2:
                        phone_part = parts[1].strip()
                        # Use just the phone number, not the name
                        merged_rec['recommender'] = phone_part
                elif not orig_recommender or orig_recommender == 'Unknown':
                    # No original recommender, use enhanced (but only if it's a phone number, not a name)
                    # Check if it looks like a phone number (contains digits)
                    if re.search(r'\d', enhanced_recommender):
                        merged_rec['recommender'] = enhanced_recommender
            
            merged.append(merged_rec)
        else:
            # No match found, keep original
            merged.append(orig_rec)
    
    return merged

