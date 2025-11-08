from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateTimeLocalField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from TaskNest.models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    class_name = StringField('Class/Year', validators=[Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


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