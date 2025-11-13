"""API route handlers."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Query
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List

from backend.database import Session as DBSession, Result, get_db
from backend.schemas import (
    UploadResponse, StatusResponse, ResultsResponse, HealthResponse, SessionInfoResponse
)
from backend.services import process_upload
from backend.config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
@router.head("/health")
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Upload and process a zip file containing WhatsApp chat and VCF files.
    
    Returns session_id for tracking processing status.
    """
    logger.info(
        f"Upload endpoint called - filename: {file.filename}, "
        f"content_type: {file.content_type}, size: {file.size if hasattr(file, 'size') else 'unknown'}"
    )
    # Validate file type
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")
    
    # Validate file size
    logger.info("Reading file content...")
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(f"File read successfully - size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum of {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Create session
    session = DBSession()
    db.add(session)
    db.commit()
    db.refresh(session)
    session_id = session.id
    
    # Save uploaded file to temporary location
    temp_file = None
    try:
        temp_file = Path(tempfile.mkdtemp()) / f"{session_id}.zip"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_file, 'wb') as f:
            f.write(file_content)
        
        # Update session status to processing
        session.status = "processing"  # type: ignore
        session.progress_message = "Starting file processing..."  # type: ignore
        db.commit()
        
        # Start background processing task
        background_tasks.add_task(
            process_upload_task,
            str(session_id),
            temp_file
        )
        
        logger.info(f"Upload successful - session_id: {session_id}")
        return UploadResponse(session_id=session_id, status="processing")  # type: ignore
        
    except Exception as e:
        logger.error(f"Upload failed - error: {str(e)}", exc_info=True)
        # Clean up on error
        if temp_file and temp_file.exists():
            temp_file.unlink()
        session.status = "error"  # type: ignore
        session.error_message = str(e)  # type: ignore
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")


async def process_upload_task(session_id: str, zip_file_path: Path):
    """
    Background task to process uploaded file.
    
    Updates session status and stores results in database.
    """
    from backend.database import SessionLocal
    
    # Create new database session for background task
    task_db = SessionLocal()
    try:
        session = task_db.query(DBSession).filter(DBSession.id == UUID(session_id)).first()
        if not session:
            return
        
        try:
            # Process the upload
            result_data = await process_upload(session_id, Path(zip_file_path))
            
            # Store results
            result = Result(
                session_id=session.id,
                recommendations=result_data['recommendations'],
                openai_enhanced=result_data['openai_enhanced']
            )
            task_db.add(result)
            
            # Update session status
            session.status = "completed"  # type: ignore
            session.progress_message = None  # type: ignore
            task_db.commit()
            
        except TimeoutError:
            session.status = "timeout"  # type: ignore
            session.error_message = "Processing exceeded timeout limit"  # type: ignore
            task_db.commit()
            
        except Exception as e:
            session.status = "error"  # type: ignore
            session.error_message = str(e)  # type: ignore
            task_db.commit()
            
    finally:
        # Clean up uploaded file
        if zip_file_path.exists():
            zip_file_path.unlink()
        task_db.close()


@router.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: UUID, db: Session = Depends(get_db)):
    """Get processing status for a session."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return StatusResponse(
        status=session.status,  # type: ignore
        error_message=session.error_message,  # type: ignore
        progress_message=session.progress_message  # type: ignore
    )


@router.get("/sessions", response_model=List[SessionInfoResponse])
async def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status (pending, processing, completed, error, timeout)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of sessions to return"),
    db: Session = Depends(get_db)
):
    """
    List all sessions, optionally filtered by status.
    
    Returns session information including ID, status, creation date, and whether results are available.
    """
    query = db.query(DBSession)
    
    # Filter by status if provided
    if status:
        valid_statuses = ["pending", "processing", "completed", "error", "timeout"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        query = query.filter(DBSession.status == status)
    
    # Order by creation date (newest first) and limit
    sessions = query.order_by(DBSession.created_at.desc()).limit(limit).all()
    
    # Build response with result information
    session_list = []
    for session in sessions:
        result = db.query(Result).filter(Result.session_id == session.id).first()
        has_results = result is not None
        
        recommendation_count = None
        openai_enhanced = None
        if has_results and isinstance(result.recommendations, list):
            recommendation_count = len(result.recommendations)
            openai_enhanced = result.openai_enhanced  # type: ignore
        
        session_list.append(SessionInfoResponse(
            session_id=session.id,  # type: ignore
            created_at=session.created_at,  # type: ignore
            status=session.status,  # type: ignore
            error_message=session.error_message,  # type: ignore
            has_results=has_results,
            recommendation_count=recommendation_count,
            openai_enhanced=openai_enhanced,  # type: ignore
            expires_at=session.expires_at  # type: ignore
        ))
    
    return session_list


@router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: UUID, db: Session = Depends(get_db)):
    """Get processed results for a session."""
    from datetime import datetime
    
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if expired
    if session.expires_at < datetime.utcnow():  # type: ignore
        raise HTTPException(status_code=410, detail="Results have expired")
    
    # Get result
    result = db.query(Result).filter(Result.session_id == session_id).first()
    
    if not result:
        if session.status == "completed":  # type: ignore
            raise HTTPException(status_code=404, detail="Results not found")
        else:
            raise HTTPException(
                status_code=202,
                detail=f"Processing not complete. Status: {session.status}"  # type: ignore
            )
    
    # Check if result expired
    if result.expires_at < datetime.utcnow():  # type: ignore
        raise HTTPException(status_code=410, detail="Results have expired")
    
    return ResultsResponse(
        recommendations=result.recommendations,  # type: ignore
        openai_enhanced=result.openai_enhanced,  # type: ignore
        created_at=result.created_at  # type: ignore
    )

