from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta, timezone
from config import Config
from models import db, User, Task, Reminder, Progress, Exam
from forms import RegistrationForm, LoginForm, TaskForm, ReminderForm, ProgressForm, TwoFactorForm, Enable2FAForm
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import csv
from io import StringIO, BytesIO
import qrcode
import base64

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
scheduler = BackgroundScheduler(daemon=True)
scheduler_started = False


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def check_reminders():
    """Background task to check and send reminders"""
    try:
        with app.app_context():
            now = datetime.now(timezone.utc)
            print(f"[CHECK] Reminder check running at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Get all unsent reminders
            all_unsent = Reminder.query.filter(Reminder.is_sent == False).all()
            print(f"[INFO] Total unsent reminders in database: {len(all_unsent)}")
            
            # Check which ones are due
            pending_reminders = Reminder.query.filter(
                Reminder.reminder_time <= now,
                Reminder.is_sent == False
            ).all()
            
            print(f"[INFO] Reminders due now: {len(pending_reminders)}")
            
            for reminder in pending_reminders:
                # In a production app, you would send email/push notification here
                print(f"[REMINDER] TRIGGERED: {reminder.title} - {reminder.message}")
                print(f"   User: {reminder.user.username} (ID: {reminder.user_id})")
                print(f"   Scheduled: {reminder.reminder_time}")
                print(f"   Current: {now}")
                reminder.is_sent = True
            
            if pending_reminders:
                db.session.commit()
                print(f"[SUCCESS] Marked {len(pending_reminders)} reminder(s) as sent")
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
            # Remove existing job if present
            if scheduler.get_job('reminder_check'):
                scheduler.remove_job('reminder_check')
            
            # Start the scheduler first
            if not scheduler.running:
                scheduler.start()
                print("[DEBUG] APScheduler started")
            
            # Add the job
            scheduler.add_job(
                func=check_reminders, 
                trigger="interval", 
                seconds=30, 
                id='reminder_check',
                replace_existing=True,
                max_instances=1
            )
            
            scheduler_started = True
            print("[SUCCESS] Reminder scheduler started successfully (checks every 30 seconds)")
            print(f"[INFO] Scheduler running: {scheduler.running}")
            print(f"[INFO] Jobs scheduled: {len(scheduler.get_jobs())}")
            print(f"[INFO] Next check in 30 seconds")
            
            # Run an immediate test check (in 3 seconds)
            scheduler.add_job(
                func=check_reminders,
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=3),
                id='test_check'
            )
            print("[INFO] Test check scheduled for 3 seconds from now")
            
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
        
        if not user:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form=form)
        
        # Check if account is locked
        if user.is_account_locked():
            lockout_time = (user.account_locked_until - datetime.utcnow()).total_seconds() / 60
            flash(f'Account is locked due to multiple failed login attempts. Try again in {int(lockout_time)} minutes.', 'danger')
            return render_template('login.html', form=form)
        
        # Verify password
        if not user.check_password(form.password.data):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts for 15 minutes
            if user.failed_login_attempts >= 5:
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()
                flash('Account locked due to too many failed login attempts. Please try again in 15 minutes.', 'danger')
            else:
                remaining_attempts = 5 - user.failed_login_attempts
                db.session.commit()
                flash(f'Invalid password. {remaining_attempts} attempts remaining before account lockout.', 'danger')
            
            return render_template('login.html', form=form)
        
        # Reset failed attempts on successful password verification
        user.failed_login_attempts = 0
        user.account_locked_until = None
        
        # Check if 2FA is enabled
        if user.two_factor_enabled:
            # Store user_id in session temporarily for 2FA verification
            session['pending_2fa_user_id'] = user.id
            db.session.commit()
            return redirect(url_for('verify_2fa'))
        
        # Complete login if no 2FA
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user)
        next_page = request.args.get('next')
        flash(f'Welcome back, {user.full_name or user.username}!', 'success')
        return redirect(next_page) if next_page else redirect(url_for('dashboard'))
    
    return render_template('login.html', form=form)


@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    """Verify 2FA token during login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        flash('Invalid session. Please login again.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_2fa_user_id', None)
        flash('User not found.', 'danger')
        return redirect(url_for('login'))
    
    form = TwoFactorForm()
    if form.validate_on_submit():
        if user.verify_2fa_token(form.token.data):
            # Clear the pending session
            session.pop('pending_2fa_user_id', None)
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Complete login
            login_user(user)
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')
    
    return render_template('verify_2fa.html', form=form)
    
    return render_template('login.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
@csrf.exempt
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
    
    # Calculate active tasks (pending + in_progress)
    active_tasks = Task.query.filter_by(user_id=current_user.id)\
        .filter(Task.status.in_(['pending', 'in_progress'])).count()
    
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
                         pending_tasks=active_tasks,  # This now includes both pending and in_progress
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
            # Get deadline from form (this is in user's LOCAL time)
            deadline_local = form.deadline.data
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            
            # Validate deadline is in the future (using local time)
            if deadline_local <= now_local:
                flash('Deadline must be in the future.', 'warning')
                return render_template('task_form.html', form=form, title='New Task')
            
            # Convert local time to UTC
            utc_offset = now_local - now_utc.replace(tzinfo=None)
            deadline_utc = deadline_local - utc_offset
            
            task = Task(
                title=form.title.data.strip(),
                description=form.description.data.strip() if form.description.data else None,
                category=form.category.data,
                priority=form.priority.data,
                deadline=deadline_utc,
                user_id=current_user.id
            )
            db.session.add(task)
            db.session.commit()
            
            # Create automatic reminder 1 day before deadline
            reminder_time_utc = deadline_utc - timedelta(days=1)
            if reminder_time_utc > now_utc:
                reminder = Reminder(
                    title=f"Reminder: {task.title}",
                    message=f"Your task '{task.title}' is due tomorrow!",
                    reminder_time=reminder_time_utc,
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
            # Get deadline from form (local time) and convert to UTC
            deadline_local = form.deadline.data
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            utc_offset = now_local - now_utc.replace(tzinfo=None)
            deadline_utc = deadline_local - utc_offset
            
            # Validate deadline is in the future for non-completed tasks
            if task.status != 'completed' and deadline_local <= now_local:
                flash('Deadline must be in the future for active tasks.', 'warning')
                return render_template('task_form.html', form=form, title='Edit Task', task=task)
            
            task.title = form.title.data.strip()
            task.description = form.description.data.strip() if form.description.data else None
            task.category = form.category.data
            task.priority = form.priority.data
            task.deadline = deadline_utc
            task.updated_at = now_utc
            
            db.session.commit()
            flash('Task updated successfully!', 'success')
            return redirect(url_for('tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating task: {str(e)}', 'danger')
    
    return render_template('task_form.html', form=form, title='Edit Task', task=task)


@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
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
@csrf.exempt
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
            # Get the datetime from the form (this is in user's LOCAL time, but naive)
            reminder_time_local = form.reminder_time.data
            
            # Get current times for comparison
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            
            # Validate reminder time is in the future (using local time)
            if reminder_time_local <= now_local:
                flash('Reminder time must be in the future.', 'warning')
                return render_template('reminder_form.html', form=form, title='New Reminder')
            
            # Calculate the time difference between local and UTC
            utc_offset = now_local - now_utc.replace(tzinfo=None)
            
            # Convert local time to UTC by subtracting the offset
            # Remove tzinfo before storing (SQLite stores as naive datetime in UTC)
            reminder_time_utc = reminder_time_local - utc_offset
            
            reminder = Reminder(
                title=form.title.data.strip(),
                message=form.message.data.strip() if form.message.data else None,
                reminder_time=reminder_time_utc,
                user_id=current_user.id
            )
            db.session.add(reminder)
            db.session.commit()
            
            print(f"[REMINDER] Created new reminder: {reminder.title}")
            print(f"[REMINDER] User entered (Local): {reminder_time_local}")
            print(f"[REMINDER] Stored as (UTC): {reminder_time_utc}")
            print(f"[REMINDER] Current Local Time: {now_local}")
            print(f"[REMINDER] Current UTC Time: {now_utc}")
            print(f"[REMINDER] UTC Offset: {utc_offset}")
            
            flash('Reminder set successfully!', 'success')
            return redirect(url_for('reminders'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating reminder: {str(e)}', 'danger')
            import traceback
            traceback.print_exc()
    
    return render_template('reminder_form.html', form=form, title='New Reminder')


@app.route('/reminder/<int:reminder_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
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


@app.route('/security')
@login_required
def security():
    """Security settings page"""
    return render_template('security.html')


@app.route('/enable-2fa', methods=['GET', 'POST'])
@login_required
def enable_2fa():
    """Enable 2FA for the current user"""
    if current_user.two_factor_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('security'))
    
    # Generate QR code
    if not current_user.two_factor_secret:
        current_user.generate_2fa_secret()
        db.session.commit()
    
    form = Enable2FAForm()
    
    if form.validate_on_submit():
        # Verify the token before enabling
        if current_user.verify_2fa_token(form.token.data):
            current_user.two_factor_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled successfully!', 'success')
            return redirect(url_for('security'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')
    
    # Generate QR code
    uri = current_user.get_2fa_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for display
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('enable_2fa.html', form=form, qr_code=img_str, secret=current_user.two_factor_secret)


@app.route('/disable-2fa', methods=['POST'])
@login_required
@csrf.exempt
def disable_2fa():
    """Disable 2FA for the current user"""
    try:
        if not current_user.two_factor_enabled:
            return jsonify({'error': 'Two-factor authentication is not enabled'}), 400
        
        current_user.two_factor_enabled = False
        current_user.two_factor_secret = None
        db.session.commit()
        
        flash('Two-factor authentication has been disabled.', 'success')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
@csrf.exempt
def api_check_reminders():
    """Check for pending reminders for current user"""
    try:
        now = datetime.now(timezone.utc)
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
                'message': reminder.message or 'Reminder alert!',
                'time': reminder.reminder_time.strftime('%B %d, %Y at %I:%M %p')
            })
        
        print(f"[REMINDER] API: Found {len(reminders_data)} pending reminders for user {current_user.username}")
        print(f"[REMINDER] API: Current time: {now}")
        if reminders_data:
            print(f"[REMINDER] API: Returning reminders: {[r['title'] for r in reminders_data]}")
        return jsonify(reminders_data)
    except Exception as e:
        print(f"[ERROR] API Error in check-reminders: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/mark-reminder-seen/<int:reminder_id>', methods=['POST'])
@login_required
@csrf.exempt
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


if __name__ == '__main__':
    # Start the scheduler only in the main process (not in reloader child process)
    import os
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # This is the reloader child process
        start_scheduler()
        print("[INFO] Scheduler started in main worker process")
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)
