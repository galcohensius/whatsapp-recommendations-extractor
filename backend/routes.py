"""API route handlers."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.database import Session as DBSession, Result, get_db
from backend.schemas import (
    UploadResponse, StatusResponse, ResultsResponse, HealthResponse
)
from backend.services import process_upload
from backend.config import settings

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
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
    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
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
        session.status = "processing"
        db.commit()
        
        # Start background processing task
        background_tasks.add_task(
            process_upload_task,
            str(session_id),
            temp_file
        )
        
        return UploadResponse(session_id=session_id, status="processing")
        
    except Exception as e:
        # Clean up on error
        if temp_file and temp_file.exists():
            temp_file.unlink()
        session.status = "error"
        session.error_message = str(e)
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
            session.status = "completed"
            task_db.commit()
            
        except TimeoutError:
            session.status = "timeout"
            session.error_message = "Processing exceeded timeout limit"
            task_db.commit()
            
        except Exception as e:
            session.status = "error"
            session.error_message = str(e)
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
        status=session.status,
        error_message=session.error_message
    )


@router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: UUID, db: Session = Depends(get_db)):
    """Get processed results for a session."""
    from datetime import datetime
    
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if expired
    if session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Results have expired")
    
    # Get result
    result = db.query(Result).filter(Result.session_id == session_id).first()
    
    if not result:
        if session.status == "completed":
            raise HTTPException(status_code=404, detail="Results not found")
        else:
            raise HTTPException(
                status_code=202,
                detail=f"Processing not complete. Status: {session.status}"
            )
    
    # Check if result expired
    if result.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Results have expired")
    
    return ResultsResponse(
        recommendations=result.recommendations,
        openai_enhanced=result.openai_enhanced,
        created_at=result.created_at
    )

