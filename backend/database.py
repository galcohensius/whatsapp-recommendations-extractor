"""Database models and setup using SQLAlchemy."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Boolean, Text, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

from backend.config import settings

Base = declarative_base()


class Session(Base):
    """Session model for tracking uploads and processing status."""
    
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True
    )  # pending, processing, completed, error, timeout
    error_message = Column(Text, nullable=True)
    progress_message = Column(Text, nullable=True)
    expires_at = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(days=settings.RETENTION_DAYS),
        nullable=False,
        index=True
    )
    
    # Relationship
    result = relationship("Result", back_populates="session", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_sessions_expires_at', 'expires_at'),
        Index('idx_sessions_created_at', 'created_at'),
    )


class Result(Base):
    """Result model for storing processed recommendations."""
    
    __tablename__ = "results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, unique=True, index=True)
    recommendations = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(days=settings.RETENTION_DAYS),
        nullable=False,
        index=True
    )
    openai_enhanced = Column(Boolean, default=False, nullable=False)
    
    # Relationship
    session = relationship("Session", back_populates="result")
    
    __table_args__ = (
        Index('idx_results_expires_at', 'expires_at'),
    )


# Database engine and session factory
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

