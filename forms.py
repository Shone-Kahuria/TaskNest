from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateTimeLocalField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp
from models import User
import re

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters'),
        Regexp('^[A-Za-z0-9_]+$', message='Username can only contain letters, numbers, and underscores')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address')
    ])
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(max=120, message='Full name cannot exceed 120 characters')
    ])
    class_name = StringField('Class/Year', validators=[Length(max=50)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Sign Up')
    
    def validate_username(self, username):
        # Check for profanity or inappropriate words
        inappropriate_words = ['admin', 'root', 'system', 'test']
        if username.data.lower() in inappropriate_words:
            raise ValidationError('This username is not allowed.')
        
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')
    
    def validate_password(self, password):
        """Enhanced password validation"""
        pwd = password.data
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError('Password must contain at least one uppercase letter')
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', pwd):
            raise ValidationError('Password must contain at least one lowercase letter')
        
        # Check for at least one digit
        if not re.search(r'\d', pwd):
            raise ValidationError('Password must contain at least one number')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pwd):
            raise ValidationError('Password must contain at least one special character (!@#$%^&*...)')
        
        # Check for common weak passwords
        weak_passwords = ['password', 'Password123', '12345678', 'qwerty123']
        if pwd in weak_passwords:
            raise ValidationError('This password is too common. Please choose a stronger password.')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


class TwoFactorForm(FlaskForm):
    token = StringField('Authentication Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Code must be exactly 6 digits'),
        Regexp(r'^\d{6}$', message='Code must be 6 digits')
    ])
    submit = SubmitField('Verify')


class Enable2FAForm(FlaskForm):
    token = StringField('Verification Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Code must be exactly 6 digits')
    ])
    submit = SubmitField('Enable 2FA')


class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    category = SelectField('Category', choices=[
        ('general', 'General'),
        ('assignment', 'Assignment'),
        ('project', 'Project'),
        ('exam', 'Exam'),
        ('cat', 'CAT')
    ])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ])
    deadline = DateTimeLocalField('Deadline', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    submit = SubmitField('Save Task')


class ReminderForm(FlaskForm):
    title = StringField('Reminder Title', validators=[DataRequired(), Length(max=200)])
    message = TextAreaField('Message')
    reminder_time = DateTimeLocalField('Reminder Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    submit = SubmitField('Set Reminder')


class ProgressForm(FlaskForm):
    progress_percentage = SelectField('Progress', choices=[
        (0, '0%'), (10, '10%'), (20, '20%'), (30, '30%'), (40, '40%'),
        (50, '50%'), (60, '60%'), (70, '70%'), (80, '80%'), (90, '90%'), (100, '100%')
    ], coerce=int)
    notes = TextAreaField('Notes')
    submit = SubmitField('Update Progress')