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
from uuid import UUID

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extract_txt_and_vcf import (
    parse_all_vcf_files,
    parse_all_chat_files,
    extract_text_recommendations,
    extract_vcf_mentions,
    include_unmentioned_vcf_files
)
from data_cleanup import pre_enhancement_cleanup, post_enhancement_cleanup
from ai_enhance_recommendations import (
    enhance_recommendations_with_openai
)
from backend.config import settings
from backend.database import SessionLocal, Session as DBSession


def update_progress_message(session_id: str, message: str) -> None:
    """
    Update the progress message for a session in the database.
    
    Args:
        session_id: Session ID string
        message: Progress message to set
    """
    try:
        db = SessionLocal()
        try:
            session = db.query(DBSession).filter(DBSession.id == UUID(session_id)).first()
            if session:
                session.progress_message = message  # type: ignore
                db.commit()
        finally:
            db.close()
    except Exception as e:
        # Don't fail processing if progress update fails
        print(f"[{session_id}] Warning: Failed to update progress message: {e}")


def process_upload_sync(session_id: str, zip_file_path: Path, preview_mode: bool = False) -> Dict:
    """
    Process uploaded zip file synchronously.
    
    Args:
        session_id: Session ID for tracking
        zip_file_path: Path to uploaded zip file
        preview_mode: If True, limit to last N recommendations (after deduplication)
        
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
        update_progress_message(session_id, "Parsing VCF contact files...")
        vcf_data = parse_all_vcf_files(vcf_dir)
        print(f"[{session_id}]   Found {len(vcf_data)} .vcf files")
        
        print(f"[{session_id}] Step 2: Parsing WhatsApp chat files...")
        update_progress_message(session_id, "Parsing WhatsApp chat files...")
        all_messages = parse_all_chat_files(text_dir)
        print(f"[{session_id}]   Found {len(all_messages)} messages")
        
        # Extract recommendations
        print(f"[{session_id}] Step 3: Extracting text recommendations...")
        update_progress_message(session_id, "Extracting text recommendations from chat...")
        text_recs = extract_text_recommendations(all_messages, vcf_data)
        print(f"[{session_id}]   Found {len(text_recs)} text recommendations")
        
        print(f"[{session_id}] Step 4: Extracting .vcf mentions from chat...")
        update_progress_message(session_id, "Extracting VCF file mentions from chat...")
        vcf_mentions, mentioned_filenames = extract_vcf_mentions(all_messages, vcf_data)
        print(f"[{session_id}]   Found {len(vcf_mentions)} .vcf file mentions")
        
        print(f"[{session_id}] Step 5: Including unmentioned .vcf files...")
        update_progress_message(session_id, "Including unmentioned VCF files...")
        unmentioned_vcf = include_unmentioned_vcf_files(vcf_data, mentioned_filenames)
        print(f"[{session_id}]   Found {len(unmentioned_vcf)} unmentioned .vcf files")
        
        # Merge all recommendations
        print(f"[{session_id}] Step 6: Merging all recommendations...")
        update_progress_message(session_id, "Merging and deduplicating recommendations...")
        all_recommendations = text_recs + vcf_mentions + unmentioned_vcf
        
        # Remove duplicates (same logic as extract_recommendations)
        import re as re_module
        seen = {}
        unique_recs = []
        
        for rec in all_recommendations:
            name = (rec.get('name') or '').strip()
            phone = (rec.get('phone') or '').strip()
            phone_normalized = re_module.sub(r'[\s+\-()]', '', phone)
            # Normalize +972 prefix to 0 for consistent duplicate detection
            if phone_normalized.startswith('972'):
                phone_normalized = '0' + phone_normalized[3:]
            
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
        
        # Limit to last N recommendations if preview mode is enabled
        if preview_mode and len(unique_recs) > settings.MAX_RECOMMENDATIONS:
            print(f"[{session_id}] Step 6.5: Limiting to last {settings.MAX_RECOMMENDATIONS} recommendations (preview mode)...")
            update_progress_message(session_id, f"Limiting to last {settings.MAX_RECOMMENDATIONS} recommendations...")
            
            # Sort by date (most recent first), handling None dates and various date formats
            from datetime import datetime
            
            def get_sort_key(rec):
                date = rec.get('date')
                if date is None:
                    return (0, datetime.min)  # Put None dates at the end
                
                # Try to parse as datetime if it's a string
                if isinstance(date, str):
                    try:
                        # Try common date formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y, %H:%M', '%Y-%m-%d', '%d/%m/%Y']:
                            try:
                                parsed_date = datetime.strptime(date, fmt)
                                return (1, parsed_date)
                            except ValueError:
                                continue
                        # If no format matches, use string comparison (lexicographic)
                        return (1, date)
                    except Exception:
                        return (1, date)
                
                # If it's already a datetime object
                if isinstance(date, datetime):
                    return (1, date)
                
                # For other types, convert to string
                return (1, str(date))
            
            unique_recs.sort(key=get_sort_key, reverse=True)
            
            # Keep only the last MAX_RECOMMENDATIONS
            original_count = len(unique_recs)
            unique_recs = unique_recs[:settings.MAX_RECOMMENDATIONS]
            print(f"[{session_id}]   Limited from {original_count} to {len(unique_recs)} recommendations")
        
        # Pre-enhancement cleanup
        print(f"[{session_id}] Step 7: Pre-enhancement cleanup...")
        update_progress_message(session_id, f"Cleaning {len(unique_recs)} recommendations...")
        recommendations, cleanup_stats = pre_enhancement_cleanup(unique_recs, messages=all_messages)
        print(f"[{session_id}]   Fixed {cleanup_stats.get('duplicates_removed', 0)} duplicates")
        print(f"[{session_id}]   Removed {cleanup_stats.get('personal_contacts_removed', 0)} personal contacts")
        
        # OpenAI enhancement (single pass with smart context windows)
        openai_enhanced = False
        if settings.OPENAI_API_KEY:
            print(f"[{session_id}] Step 8: Enhancing with OpenAI...")
            null_count_before = sum(1 for r in recommendations if not r.get('service'))
            update_progress_message(
                session_id, 
                f"Enhancing {len(recommendations)} recommendations with AI ({null_count_before} need service extraction)..."
            )
            try:
                print(f"[{session_id}]   {null_count_before} entries with null service (extended context)")
                print(f"[{session_id}]   {len(recommendations) - null_count_before} entries with existing service (normal context)")
                
                result = enhance_recommendations_with_openai(
                    recommendations,
                    all_messages,
                    model="gpt-4o-mini",
                    api_key=settings.OPENAI_API_KEY
                )
                
                if result['success']:
                    recommendations = result['enhanced']
                    openai_enhanced = True
                    null_count_after = sum(1 for r in recommendations if not r.get('service'))
                    extracted_count = null_count_before - null_count_after
                    print(f"[{session_id}]   Extracted services for {extracted_count} recommendations")
                    print(f"[{session_id}]   OpenAI enhancement completed")
                    update_progress_message(
                        session_id,
                        f"AI enhancement complete: extracted services for {extracted_count} recommendations"
                    )
                else:
                    print(f"[{session_id}]   OpenAI enhancement failed: {result.get('error', 'Unknown error')}")
                    update_progress_message(session_id, "AI enhancement failed, continuing with existing data...")
            except Exception as e:
                print(f"[{session_id}]   OpenAI enhancement error: {e}")
                update_progress_message(session_id, "AI enhancement error, continuing with existing data...")
        
        # Post-enhancement cleanup
        if openai_enhanced:
            print(f"[{session_id}] Step 9: Post-enhancement cleanup...")
            update_progress_message(session_id, "Final cleanup and validation...")
            recommendations, post_stats = post_enhancement_cleanup(recommendations)
            if post_stats.get('null_services_removed', 0) > 0:
                print(f"[{session_id}]   Removed {post_stats.get('null_services_removed', 0)} entries with null service")
            if post_stats.get('services_cleaned', 0) > 0:
                print(f"[{session_id}]   Cleaned {post_stats.get('services_cleaned', 0)} service fields")
        
        update_progress_message(session_id, f"Processing complete! Found {len(recommendations)} recommendations.")
        
        return {
            'recommendations': recommendations,
            'openai_enhanced': openai_enhanced
        }
        
    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def process_upload(session_id: str, zip_file_path: Path, preview_mode: bool = False) -> Dict:
    """
    Process uploaded zip file asynchronously with timeout.
    
    Args:
        session_id: Session ID for tracking
        zip_file_path: Path to uploaded zip file
        preview_mode: If True, limit to last N recommendations
        
    Returns:
        Dictionary with 'recommendations' list and 'openai_enhanced' boolean
        
    Raises:
        TimeoutError: If processing takes longer than PROCESSING_TIMEOUT
    """
    try:
        # Run sync processing in executor with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, process_upload_sync, session_id, zip_file_path, preview_mode),
            timeout=settings.PROCESSING_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"Processing exceeded {settings.PROCESSING_TIMEOUT} seconds timeout")

