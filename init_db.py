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

def reset_database():
    """Drop all tables and recreate them (WARNING: Deletes all data!)"""
    with app.app_context():
        print("WARNING: This will delete all data!")
        confirm = input("Type 'yes' to confirm: ")
        
        if confirm.lower() == 'yes':
            print("Dropping all tables...")
            db.drop_all()
            print("Creating tables...")
            db.create_all()
            print("✓ Database reset complete!")
        else:
            print("Operation cancelled.")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            init_database()
        elif command == 'test-user':
            create_test_user()
        elif command == 'reset':
            reset_database()
        else:
            print("Unknown command. Use: init, test-user, or reset")
    else:
        print("TaskNest Database Management")
        print("\nUsage:")
        print("  python init_db.py init        - Initialize database")
        print("  python init_db.py test-user   - Create test user")
        print("  python init_db.py reset       - Reset database (deletes all data)")