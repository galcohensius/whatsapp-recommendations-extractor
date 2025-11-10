"""Background cleanup task for expired sessions and results."""

from datetime import datetime
from backend.database import SessionLocal, Session, Result
from backend.config import settings


def cleanup_expired_data():
    """Delete sessions and results older than retention period."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        
        # Delete expired results first (due to foreign key constraint)
        expired_results = db.query(Result).filter(Result.expires_at < now).all()
        result_count = len(expired_results)
        for result in expired_results:
            db.delete(result)
        
        # Delete expired sessions
        expired_sessions = db.query(Session).filter(Session.expires_at < now).all()
        session_count = len(expired_sessions)
        for session in expired_sessions:
            db.delete(session)
        
        db.commit()
        
        print(f"Cleanup: Deleted {result_count} expired results and {session_count} expired sessions")
        
        return {
            'results_deleted': result_count,
            'sessions_deleted': session_count
        }
    except Exception as e:
        db.rollback()
        print(f"Cleanup error: {e}")
        raise
    finally:
        db.close()

