#!/usr/bin/env python3
"""
Migration script to add progress_message column to sessions table.
Run this once to update the database schema.
"""

from sqlalchemy import text
from backend.database import engine

def migrate():
    """Add progress_message column to sessions table if it doesn't exist."""
    with engine.connect() as conn:
        # Check if column exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='sessions' AND column_name='progress_message'
        """)
        result = conn.execute(check_query)
        exists = result.fetchone() is not None
        
        if exists:
            print("Column 'progress_message' already exists. No migration needed.")
            return
        
        # Add the column
        print("Adding 'progress_message' column to 'sessions' table...")
        alter_query = text("""
            ALTER TABLE sessions 
            ADD COLUMN progress_message TEXT
        """)
        conn.execute(alter_query)
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()

