"""Processing service that wraps existing extraction logic."""

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
import asyncio
import signal

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extract_txt_and_vcf import (
    parse_all_vcf_files,
    parse_all_chat_files,
    extract_text_recommendations,
    extract_vcf_mentions,
    include_unmentioned_vcf_files
)
from data_cleanup import fix_recommendations
from ai_enhance_recommendations import (
    enhance_recommendations_with_openai,
    enhance_null_services_with_openai
)
from backend.config import settings


def process_upload_sync(session_id: str, zip_file_path: Path) -> Dict:
    """
    Process uploaded zip file synchronously.
    
    Args:
        session_id: Session ID for tracking
        zip_file_path: Path to uploaded zip file
        
    Returns:
        Dictionary with 'recommendations' list and 'openai_enhanced' boolean
    """
    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix=f"whatsapp_extract_{session_id}_"))
        
        # Extract zip file
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Create data directory structure
        data_dir = temp_dir / "data"
        vcf_dir = data_dir / "vcf"
        text_dir = data_dir / "txt"
        vcf_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)
        
        # Move .vcf files to vcf directory
        for vcf_file in temp_dir.rglob("*.vcf"):
            if vcf_file.parent != vcf_dir:
                shutil.move(str(vcf_file), str(vcf_dir / vcf_file.name))
        
        # Move .txt files to txt directory
        for txt_file in temp_dir.rglob("*.txt"):
            if txt_file.parent != text_dir:
                shutil.move(str(txt_file), str(text_dir / txt_file.name))
        
        # Parse files
        print(f"[{session_id}] Step 1: Parsing .vcf files...")
        vcf_data = parse_all_vcf_files(vcf_dir)
        print(f"[{session_id}]   Found {len(vcf_data)} .vcf files")
        
        print(f"[{session_id}] Step 2: Parsing WhatsApp chat files...")
        all_messages = parse_all_chat_files(text_dir)
        print(f"[{session_id}]   Found {len(all_messages)} messages")
        
        # Extract recommendations
        print(f"[{session_id}] Step 3: Extracting text recommendations...")
        text_recs = extract_text_recommendations(all_messages, vcf_data)
        print(f"[{session_id}]   Found {len(text_recs)} text recommendations")
        
        print(f"[{session_id}] Step 4: Extracting .vcf mentions from chat...")
        vcf_mentions, mentioned_filenames = extract_vcf_mentions(all_messages, vcf_data)
        print(f"[{session_id}]   Found {len(vcf_mentions)} .vcf file mentions")
        
        print(f"[{session_id}] Step 5: Including unmentioned .vcf files...")
        unmentioned_vcf = include_unmentioned_vcf_files(vcf_data, mentioned_filenames)
        print(f"[{session_id}]   Found {len(unmentioned_vcf)} unmentioned .vcf files")
        
        # Merge all recommendations
        print(f"[{session_id}] Step 6: Merging all recommendations...")
        all_recommendations = text_recs + vcf_mentions + unmentioned_vcf
        
        # Remove duplicates (same logic as extract_recommendations)
        import re as re_module
        seen = {}
        unique_recs = []
        
        for rec in all_recommendations:
            name = rec.get('name', '').strip()
            phone = rec.get('phone', '').strip()
            phone_normalized = re_module.sub(r'[\s+\-()]', '', phone)
            
            key = (name.lower(), phone_normalized)
            
            if key in seen:
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
                    unique_recs.remove(existing)
                    unique_recs.append(rec)
                    seen[key] = rec
            else:
                seen[key] = rec
                unique_recs.append(rec)
        
        print(f"[{session_id}]   Total unique recommendations: {len(unique_recs)}")
        
        # Fix/cleanup recommendations
        print(f"[{session_id}] Step 7: Cleaning up recommendations...")
        # Create temporary JSON file for fix_recommendations
        temp_json = temp_dir / "temp_recommendations.json"
        with open(temp_json, 'w', encoding='utf-8') as f:
            json.dump(unique_recs, f, ensure_ascii=False, indent=2)
        
        fix_result = fix_recommendations(temp_json, temp_json)
        print(f"[{session_id}]   Fixed {fix_result.get('duplicates_removed', 0)} duplicates")
        
        # Reload fixed recommendations
        with open(temp_json, 'r', encoding='utf-8') as f:
            recommendations = json.load(f)
        
        # OpenAI enhancement
        openai_enhanced = False
        if settings.OPENAI_API_KEY:
            print(f"[{session_id}] Step 8: Enhancing with OpenAI...")
            try:
                # First pass: Full enhancement
                result = enhance_recommendations_with_openai(
                    recommendations,
                    all_messages,
                    model="gpt-4o-mini",
                    api_key=settings.OPENAI_API_KEY
                )
                
                if result['success']:
                    recommendations = result['enhanced']
                    openai_enhanced = True
                    
                    # Second pass: Extract services for null entries
                    null_count = sum(1 for r in recommendations if not r.get('service'))
                    if null_count > 0:
                        result2 = enhance_null_services_with_openai(
                            recommendations,
                            all_messages,
                            model="gpt-4o-mini",
                            api_key=settings.OPENAI_API_KEY
                        )
                        if result2['success']:
                            recommendations = result2['enhanced']
                    
                    print(f"[{session_id}]   OpenAI enhancement completed")
                else:
                    print(f"[{session_id}]   OpenAI enhancement failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"[{session_id}]   OpenAI enhancement error: {e}")
        
        return {
            'recommendations': recommendations,
            'openai_enhanced': openai_enhanced
        }
        
    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def process_upload(session_id: str, zip_file_path: Path) -> Dict:
    """
    Process uploaded zip file asynchronously with timeout.
    
    Args:
        session_id: Session ID for tracking
        zip_file_path: Path to uploaded zip file
        
    Returns:
        Dictionary with 'recommendations' list and 'openai_enhanced' boolean
        
    Raises:
        TimeoutError: If processing takes longer than PROCESSING_TIMEOUT
    """
    try:
        # Run sync processing in executor with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, process_upload_sync, session_id, zip_file_path),
            timeout=settings.PROCESSING_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"Processing exceeded {settings.PROCESSING_TIMEOUT} seconds timeout")

