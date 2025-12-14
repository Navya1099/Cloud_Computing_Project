from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
import hashlib
import os

auth_bp = Blueprint('auth', __name__)

# Database configuration - uses Firestore on GCP, falls back to in-memory for local dev
USE_FIRESTORE = os.environ.get('USE_FIRESTORE', 'false').lower() == 'true'

# In-memory fallback for local development
_local_users = {}

def get_firestore_client():
    """Get Firestore client (lazy loading)"""
    try:
        from google.cloud import firestore
        return firestore.Client()
    except Exception as e:
        print(f"Firestore not available: {e}")
        return None

def get_user(username):
    """Get user from database"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            doc = db.collection('users').document(username).get()
            if doc.exists:
                return doc.to_dict()
        return None
    else:
        return _local_users.get(username)

def create_user(username, email, password_hash):
    """Create user in database"""
    from datetime import datetime
    user_data = {
        'email': email,
        'password': password_hash,
        'created_at': datetime.now().isoformat()
    }
    
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            db.collection('users').document(username).set(user_data)
    else:
        _local_users[username] = user_data
    
    return user_data

def user_exists(username):
    """Check if username exists"""
    return get_user(username) is not None

def email_exists(email):
    """Check if email exists"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            users = db.collection('users').where('email', '==', email).limit(1).get()
            return len(list(users)) > 0
        return False
    else:
        return any(user['email'] == email for user in _local_users.values())

def update_user(username, update_data):
    """Update user in database"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            db.collection('users').document(username).update(update_data)
            return True
    else:
        if username in _local_users:
            _local_users[username].update(update_data)
            return True
    return False

def email_exists_for_other_user(email, current_username):
    """Check if email exists for a different user"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            users = db.collection('users').where('email', '==', email).get()
            for doc in users:
                if doc.id != current_username:
                    return True
        return False
    else:
        for uname, user in _local_users.items():
            if user['email'] == email and uname != current_username:
                return True
        return False

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = os.environ.get('PASSWORD_SALT', 'travel_expense_optimizer_salt')
    return hashlib.sha256((password + salt).encode()).hexdigest()

# Search history storage (in-memory fallback)
_local_history = {}

def save_search_history(username, search_data):
    """Save search history with best deal to database"""
    from datetime import datetime
    
    history_entry = {
        'origin': search_data.get('origin'),
        'destination': search_data.get('destination'),
        'departure_date': search_data.get('departure_date'),
        'return_date': search_data.get('return_date'),
        'adults': search_data.get('adults'),
        'best_package': search_data.get('best_package'),
        'searched_at': datetime.now().isoformat()
    }
    
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            # Add to user's history subcollection
            db.collection('users').document(username).collection('history').add(history_entry)
    else:
        if username not in _local_history:
            _local_history[username] = []
        _local_history[username].append(history_entry)

def get_search_history(username):
    """Get search history for a user"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            history_ref = db.collection('users').document(username).collection('history')
            docs = history_ref.order_by('searched_at', direction='DESCENDING').limit(20).get()
            # Include document ID for deletion
            history = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                history.append(item)
            return history
        return []
    else:
        history = _local_history.get(username, [])
        # Add index as ID for local storage
        result = []
        for i, item in enumerate(sorted(history, key=lambda x: x.get('searched_at', ''), reverse=True)[:20]):
            item_copy = item.copy()
            item_copy['id'] = str(i)
            result.append(item_copy)
        return result

def delete_history_item(username, history_id):
    """Delete a history item"""
    if USE_FIRESTORE:
        db = get_firestore_client()
        if db:
            db.collection('users').document(username).collection('history').document(history_id).delete()
            return True
    return False

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
        
        user = get_user(username)
        if user:
            if user['password'] == hash_password(password):
                session['user_id'] = username
                session['email'] = user['email']
                
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
        elif user_exists(username):
            error = 'Username already exists. Please choose another.'
        elif '@' not in email or '.' not in email:
            error = 'Please enter a valid email address.'
        elif email_exists(email):
            error = 'Email already registered. Please use another email or login.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters long.'
        elif password != confirm_password:
            error = 'Passwords do not match. Please try again.'
        else:
            # Register user
            create_user(username, email, hash_password(password))
            return redirect(url_for('auth.login', registered=True))
    
    return render_template('register.html', error=error)

@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Handle user profile view and update"""
    username = session.get('user_id')
    user = get_user(username)
    
    error = None
    success = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            new_email = request.form.get('email', '').strip()
            
            # Validation
            if '@' not in new_email or '.' not in new_email:
                error = 'Please enter a valid email address.'
            elif new_email != user.get('email') and email_exists_for_other_user(new_email, username):
                error = 'Email already in use by another account.'
            else:
                update_data = {
                    'email': new_email
                }
                if update_user(username, update_data):
                    session['email'] = new_email
                    user = get_user(username)  # Refresh user data
                    success = 'Profile updated successfully!'
                else:
                    error = 'Failed to update profile. Please try again.'
        
        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not current_password or not new_password:
                error = 'Please fill in all password fields.'
            elif user['password'] != hash_password(current_password):
                error = 'Current password is incorrect.'
            elif len(new_password) < 6:
                error = 'New password must be at least 6 characters.'
            elif new_password != confirm_password:
                error = 'New passwords do not match.'
            else:
                update_data = {'password': hash_password(new_password)}
                if update_user(username, update_data):
                    success = 'Password changed successfully!'
                else:
                    error = 'Failed to change password. Please try again.'
    
    # Format created_at for display
    created_at = user.get('created_at', '')
    if created_at:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(created_at)
            created_at = dt.strftime('%B %d, %Y')
        except:
            created_at = created_at[:10] if len(created_at) >= 10 else created_at
    
    return render_template('profile.html',
        username=username,
        email=user.get('email', ''),
        created_at=created_at,
        error=error,
        success=success
    )
