"""
Database initialization script for TaskNest
Run this script to create all database tables
"""

from app import app, db
from models import User, Task, Reminder, Progress, Exam

def init_database():
    """Initialize database and create all tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully!")
        
        # Print table information
        print("\nCreated tables:")
        print("  - users")
        print("  - tasks")
        print("  - reminders")
        print("  - progress")
        print("  - exams")
        print("\nDatabase initialization complete!")

