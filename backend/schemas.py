"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response schema for file upload."""
    session_id: UUID
    status: str = "processing"


class StatusResponse(BaseModel):
    """Response schema for status check."""
    status: str
    error_message: Optional[str] = None


class ResultsResponse(BaseModel):
    """Response schema for results."""
    recommendations: List[Dict]
    openai_enhanced: bool
    created_at: datetime


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionInfoResponse(BaseModel):
    """Response schema for session information in list."""
    session_id: UUID
    created_at: datetime
    status: str
    error_message: Optional[str] = None
    has_results: bool
    recommendation_count: Optional[int] = None
    openai_enhanced: Optional[bool] = None
    expires_at: datetime
