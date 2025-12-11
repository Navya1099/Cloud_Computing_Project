from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
import hashlib
import os

auth_bp = Blueprint('auth', __name__)

# Simple in-memory user storage (replace with database in production)
users = {}

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = os.environ.get('PASSWORD_SALT', 'travel_expense_optimizer_salt')
    return hashlib.sha256((password + salt).encode()).hexdigest()

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    error = None
    success = request.args.get('registered')
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember')
        
        if username in users:
            if users[username]['password'] == hash_password(password):
                session['user_id'] = username
                session['email'] = users[username]['email']
                
                if remember:
                    session.permanent = True
                
                return redirect(url_for('index'))
            else:
                error = 'Invalid password. Please try again.'
        else:
            error = 'Username not found. Please check your username or register.'
    
    return render_template('login.html', error=error, success='Registration successful! Please login.' if success else None)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if len(username) < 3:
            error = 'Username must be at least 3 characters long.'
        elif username in users:
            error = 'Username already exists. Please choose another.'
        elif '@' not in email or '.' not in email:
            error = 'Please enter a valid email address.'
        elif any(user['email'] == email for user in users.values()):
            error = 'Email already registered. Please use another email or login.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters long.'
        elif password != confirm_password:
            error = 'Passwords do not match. Please try again.'
        else:
            # Register user
            users[username] = {
                'email': email,
                'password': hash_password(password)
            }
            return redirect(url_for('auth.login', registered=True))
    
    return render_template('register.html', error=error)

@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    return redirect(url_for('auth.login'))
