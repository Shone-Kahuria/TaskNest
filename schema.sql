-- TaskNest Database Schema (PostgreSQL)
-- This file is for reference only - tables are created by SQLAlchemy

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    class_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'general',
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'pending',
    deadline TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

-- Reminders table
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    reminder_time TIMESTAMP NOT NULL,
    is_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE
);

-- Progress table
CREATE TABLE progress (
    id SERIAL PRIMARY KEY,
    progress_percentage INTEGER DEFAULT 0,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
);

-- Exams table
CREATE TABLE exams (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(100) NOT NULL,
    exam_type VARCHAR(50),
    exam_date TIMESTAMP NOT NULL,
    location VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for better performance
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_deadline ON tasks(deadline);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_reminders_user_id ON reminders(user_id);
CREATE INDEX idx_reminders_time ON reminders(reminder_time);
CREATE INDEX idx_progress_task_id ON progress(task_id);

-- Sample data (optional - for testing)
/*
INSERT INTO users (username, email, password_hash, full_name, class_name)
VALUES ('student', 'student@test.com', 'hashed_password_here', 'Test Student', 'Year 3');

INSERT INTO tasks (title, description, category, priority, deadline, user_id)
VALUES 
    ('Complete Math Assignment', 'Chapter 5 exercises', 'assignment', 'high', '2025-11-01 23:59:00', 1),
    ('Study for Physics CAT', 'Topics: Mechanics and Waves', 'cat', 'high', '2025-10-28 09:00:00', 1),
    ('Group Project Meeting', 'Discuss project progress', 'project', 'medium', '2025-10-26 14:00:00', 1);
*/
