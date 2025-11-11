from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
from config import Config
from models import db, User, Task, Reminder, Progress, Exam
from forms import RegistrationForm, LoginForm, TaskForm, ReminderForm, ProgressForm
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import csv
from io import StringIO

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Scheduler for reminders
scheduler = BackgroundScheduler()
scheduler_started = False


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def check_reminders():
    """Background task to check and send reminders"""
    try:
        with app.app_context():
            now = datetime.utcnow()
            pending_reminders = Reminder.query.filter(
                Reminder.reminder_time <= now,
                Reminder.is_sent == False
            ).all()
            
            for reminder in pending_reminders:
                # In a production app, you would send email/push notification here
                print(f"[REMINDER] TRIGGERED: {reminder.title} - {reminder.message}")
                print(f"   User: {reminder.user.username} (ID: {reminder.user_id})")
                print(f"   Time: {reminder.reminder_time}")
                reminder.is_sent = True
            
            if pending_reminders:
                db.session.commit()
                print(f"[SUCCESS] Marked {len(pending_reminders)} reminder(s) as sent at {now}")
            else:
                # Silent check - no output unless there's an issue
                pass
    except OperationalError as e:
        print(f"[ERROR] Database connection error in reminder check: {e}")
    except Exception as e:
        print(f"[ERROR] Error checking reminders: {e}")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """Start the background scheduler"""
    global scheduler_started
    if not scheduler_started:
        try:
            scheduler.add_job(
                func=check_reminders, 
                trigger="interval", 
                seconds=30, 
                id='reminder_check',
                replace_existing=True,
                max_instances=1
            )
            scheduler.start()
            scheduler_started = True
            print("[SUCCESS] Reminder scheduler started successfully (checks every 30 seconds)")
        except Exception as e:
            print(f"[ERROR] Error starting scheduler: {e}")
            import traceback
            traceback.print_exc()


# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(
                username=form.username.data,
                email=form.email.data,
                full_name=form.full_name.data,
                class_name=form.class_name.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred. Username or email may already exist.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
    
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    try:
        username = current_user.username
        logout_user()
        flash(f'Goodbye {username}! You have been logged out successfully.', 'success')
    except Exception as e:
        print(f"[ERROR] Logout error: {str(e)}")
        flash('An error occurred during logout.', 'error')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Get statistics
    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(user_id=current_user.id, status='completed').count()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # Get upcoming tasks
    upcoming_tasks = Task.query.filter_by(user_id=current_user.id)\
        .filter(Task.deadline >= datetime.utcnow())\
        .order_by(Task.deadline.asc())\
        .limit(5).all()
    
    # Get overdue tasks
    overdue_tasks = Task.query.filter_by(user_id=current_user.id)\
        .filter(Task.deadline < datetime.utcnow(), Task.status != 'completed')\
        .order_by(Task.deadline.asc())\
        .all()
    
    # Get upcoming reminders
    upcoming_reminders = Reminder.query.filter_by(user_id=current_user.id, is_sent=False)\
        .filter(Reminder.reminder_time >= datetime.utcnow())\
        .order_by(Reminder.reminder_time.asc())\
        .limit(5).all()
    
    # Calculate completion rate
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return render_template('dashboard.html',
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         pending_tasks=pending_tasks,
                         upcoming_tasks=upcoming_tasks,
                         overdue_tasks=overdue_tasks,
                         upcoming_reminders=upcoming_reminders,
                         completion_rate=round(completion_rate, 1))


@app.route('/tasks')
@login_required
def tasks():
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', 'all')
    search_query = request.args.get('search', '').strip()
    
    query = Task.query.filter_by(user_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if category_filter != 'all':
        query = query.filter_by(category=category_filter)
    
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern)
            )
        )
    
    tasks = query.order_by(Task.deadline.asc()).all()
    
    return render_template('tasks.html', tasks=tasks, status_filter=status_filter, 
                         category_filter=category_filter, search_query=search_query)


@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def new_task():
    form = TaskForm()
    
    if form.validate_on_submit():
        try:
            # Validate deadline is in the future
            if form.deadline.data <= datetime.utcnow():
                flash('Deadline must be in the future.', 'warning')
                return render_template('task_form.html', form=form, title='New Task')
            
            task = Task(
                title=form.title.data.strip(),
                description=form.description.data.strip() if form.description.data else None,
                category=form.category.data,
                priority=form.priority.data,
                deadline=form.deadline.data,
                user_id=current_user.id
            )
            db.session.add(task)
            db.session.commit()
            
            # Create automatic reminder 1 day before deadline
            reminder_time = form.deadline.data - timedelta(days=1)
            if reminder_time > datetime.utcnow():
                reminder = Reminder(
                    title=f"Reminder: {task.title}",
                    message=f"Your task '{task.title}' is due tomorrow!",
                    reminder_time=reminder_time,
                    user_id=current_user.id,
                    task_id=task.id
                )
                db.session.add(reminder)
                db.session.commit()
            
            flash('Task created successfully!', 'success')
            return redirect(url_for('tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating task: {str(e)}', 'danger')
    
    return render_template('task_form.html', form=form, title='New Task')


@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        flash('You do not have permission to edit this task.', 'danger')
        return redirect(url_for('tasks'))
    
    form = TaskForm(obj=task)
    
    if form.validate_on_submit():
        try:
            # Validate deadline is in the future for non-completed tasks
            if task.status != 'completed' and form.deadline.data <= datetime.utcnow():
                flash('Deadline must be in the future for active tasks.', 'warning')
                return render_template('task_form.html', form=form, title='Edit Task', task=task)
            
            task.title = form.title.data.strip()
            task.description = form.description.data.strip() if form.description.data else None
            task.category = form.category.data
            task.priority = form.priority.data
            task.deadline = form.deadline.data
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Task updated successfully!', 'success')
            return redirect(url_for('tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating task: {str(e)}', 'danger')
    
    return render_template('task_form.html', form=form, title='Edit Task', task=task)


@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        flash('You do not have permission to delete this task.', 'danger')
        return redirect(url_for('tasks'))
    
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('tasks'))


@app.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        
        # Update progress to 100%
        progress = Progress.query.filter_by(task_id=task.id).order_by(Progress.recorded_at.desc()).first()
        if not progress or progress.progress_percentage != 100:
            new_progress = Progress(
                progress_percentage=100,
                notes='Task completed',
                user_id=current_user.id,
                task_id=task.id
            )
            db.session.add(new_progress)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Task marked as complete!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/task/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Update task status via AJAX"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        new_status = request.json.get('status')
        
        if new_status not in ['pending', 'in_progress', 'completed']:
            return jsonify({'error': 'Invalid status'}), 400
        
        task.status = new_status
        
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
        else:
            task.completed_at = None
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Task status updated to {new_status.replace("_", " ").title()}'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/task/<int:task_id>/progress', methods=['GET', 'POST'])
@login_required
def task_progress(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        flash('You do not have permission to view this task.', 'danger')
        return redirect(url_for('tasks'))
    
    form = ProgressForm()
    
    if form.validate_on_submit():
        try:
            progress = Progress(
                progress_percentage=form.progress_percentage.data,
                notes=form.notes.data.strip() if form.notes.data else None,
                user_id=current_user.id,
                task_id=task.id
            )
            db.session.add(progress)
            
            # Update task status based on progress
            if form.progress_percentage.data == 100:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
            elif form.progress_percentage.data > 0 and task.status == 'pending':
                task.status = 'in_progress'
            
            task.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Progress updated successfully!', 'success')
            return redirect(url_for('task_progress', task_id=task.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating progress: {str(e)}', 'danger')
    
    progress_records = Progress.query.filter_by(task_id=task.id).order_by(Progress.recorded_at.desc()).all()
    
    return render_template('progress.html', task=task, form=form, progress_records=progress_records)


@app.route('/reminders')
@login_required
def reminders():
    upcoming_reminders = Reminder.query.filter_by(user_id=current_user.id, is_sent=False)\
        .filter(Reminder.reminder_time >= datetime.utcnow())\
        .order_by(Reminder.reminder_time.asc()).all()
    
    past_reminders = Reminder.query.filter_by(user_id=current_user.id)\
        .filter(
            (Reminder.is_sent == True) | (Reminder.reminder_time < datetime.utcnow())
        ).order_by(Reminder.reminder_time.desc()).limit(10).all()
    
    return render_template('reminders.html', upcoming_reminders=upcoming_reminders, past_reminders=past_reminders)


@app.route('/reminder/new', methods=['GET', 'POST'])
@login_required
def new_reminder():
    form = ReminderForm()
    
    if form.validate_on_submit():
        try:
            # Validate reminder time is in the future
            if form.reminder_time.data <= datetime.utcnow():
                flash('Reminder time must be in the future.', 'warning')
                return render_template('reminder_form.html', form=form, title='New Reminder')
            
            reminder = Reminder(
                title=form.title.data.strip(),
                message=form.message.data.strip() if form.message.data else None,
                reminder_time=form.reminder_time.data,
                user_id=current_user.id
            )
            db.session.add(reminder)
            db.session.commit()
            
            flash('Reminder set successfully!', 'success')
            return redirect(url_for('reminders'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating reminder: {str(e)}', 'danger')
    
    return render_template('reminder_form.html', form=form, title='New Reminder')


@app.route('/reminder/<int:reminder_id>/delete', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    
    if reminder.user_id != current_user.id:
        flash('You do not have permission to delete this reminder.', 'danger')
        return redirect(url_for('reminders'))
    
    db.session.delete(reminder)
    db.session.commit()
    flash('Reminder deleted successfully!', 'success')
    return redirect(url_for('reminders'))


@app.route('/calendar')
@login_required
def calendar():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    reminders = Reminder.query.filter_by(user_id=current_user.id, is_sent=False).all()
    
    return render_template('calendar.html', tasks=tasks, reminders=reminders)


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'),
                             'logo.jpg', mimetype='image/jpeg')


# API endpoints for calendar
@app.route('/api/tasks')
@login_required
def api_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    events = []
    for task in tasks:
        events.append({
            'id': task.id,
            'title': task.title,
            'start': task.deadline.isoformat(),
            'className': f'task-{task.priority}',
            'category': task.category,
            'status': task.status
        })
    
    return jsonify(events)


@app.route('/api/check-reminders', methods=['GET'])
@login_required
def api_check_reminders():
    """Check for pending reminders for current user"""
    try:
        now = datetime.utcnow()
        pending_reminders = Reminder.query.filter(
            Reminder.user_id == current_user.id,
            Reminder.reminder_time <= now,
            Reminder.is_sent == False
        ).all()
        
        reminders_data = []
        for reminder in pending_reminders:
            reminders_data.append({
                'id': reminder.id,
                'title': reminder.title,
                'message': reminder.message,
                'time': reminder.reminder_time.strftime('%B %d, %Y at %I:%M %p')
            })
        
        print(f"[REMINDER] API: Found {len(reminders_data)} pending reminders for user {current_user.username}")
        return jsonify(reminders_data)
    except Exception as e:
        print(f"[ERROR] API Error in check-reminders: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/mark-reminder-seen/<int:reminder_id>', methods=['POST'])
@login_required
def mark_reminder_seen(reminder_id):
    """Mark a reminder as seen/sent"""
    try:
        reminder = Reminder.query.get_or_404(reminder_id)
        
        if reminder.user_id != current_user.id:
            print(f"[ERROR] API: Unauthorized access to reminder {reminder_id}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        reminder.is_sent = True
        db.session.commit()
        
        print(f"[SUCCESS] API: Reminder {reminder_id} marked as seen")
        return jsonify({'success': True})
    except Exception as e:
        print(f"[ERROR] API Error in mark-reminder-seen: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ping', methods=['GET'])
@login_required
def api_ping():
    """Test endpoint to verify API is working"""
    return jsonify({'status': 'ok', 'message': 'API is working', 'user': current_user.username})


# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403


# Export tasks to CSV
@app.route('/tasks/export')
@login_required
def export_tasks():
    """Export user's tasks to CSV file"""
    try:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.deadline.asc()).all()
        
        # Create CSV in memory
        si = StringIO()
        writer = csv.writer(si)
        
        # Write header
        writer.writerow(['Title', 'Description', 'Category', 'Priority', 'Status', 'Deadline', 'Created', 'Completed'])
        
        # Write tasks
        for task in tasks:
            writer.writerow([
                task.title,
                task.description or '',
                task.category,
                task.priority,
                task.status,
                task.deadline.strftime('%Y-%m-%d %H:%M'),
                task.created_at.strftime('%Y-%m-%d %H:%M'),
                task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else ''
            ])
        
        output = si.getvalue()
        si.close()
        
        # Create response
        from flask import Response
        response = Response(output, mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename=tasknest_tasks_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        
        flash('Tasks exported successfully!', 'success')
        return response
        
    except Exception as e:
        flash(f'Error exporting tasks: {str(e)}', 'danger')
        return redirect(url_for('tasks'))


# Profile update route
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile information"""
    if request.method == 'POST':
        try:
            current_user.full_name = request.form.get('full_name', current_user.full_name)
            current_user.class_name = request.form.get('class_name', current_user.class_name)
            
            # Update password if provided
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            
            if current_password and new_password:
                if current_user.check_password(current_password):
                    current_user.set_password(new_password)
                    flash('Password updated successfully!', 'success')
                else:
                    flash('Current password is incorrect.', 'danger')
                    return render_template('profile_edit.html')
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
    
    return render_template('profile_edit.html')


# Create tables
with app.app_context():
    db.create_all()
    # Start the reminder scheduler
    start_scheduler()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
