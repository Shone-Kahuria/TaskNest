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

def create_test_user():
    """Create a test user for development"""
    with app.app_context():
        # Check if test user already exists
        existing_user = User.query.filter_by(username='student').first()
        if existing_user:
            print("Test user already exists!")
            return
        
        # Create test user
        test_user = User(
            username='student',
            email='student@test.com',
            full_name='Test Student',
            class_name='Year 3'
        )
        test_user.set_password('password123')
        
        db.session.add(test_user)
        db.session.commit()
        
        print("\n✓ Test user created successfully!")
        print("  Username: student")
        print("  Password: password123")

