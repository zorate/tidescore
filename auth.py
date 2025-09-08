from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from config import Config
import hashlib
import os

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Simple password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Initialize with admin user
def init_users():
    return {from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from config import Config
from models import db
import bcrypt  # ← ADD THIS IMPORT
import uuid

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# PROPER password hashing for NDPR compliance
def hash_password(password):
    """Hash password using bcrypt with salt - NDPR compliant"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password, hashed_password):
    """Verify password against bcrypt hash - NDPR compliant"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        action = request.form.get('action')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('login.html', email=email)
        
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('login.html', email=email)
        
        if action == 'signup':
            # Check if user already exists
            existing_user = db.get_user_by_email(email)
            if existing_user:
                flash('Email already registered. Please login instead.', 'error')
                return render_template('login.html', email=email)
            
            # Hash password with bcrypt (NDPR compliant)
            password_hash = hash_password(password)
            
            # Register new user
            user_id = f"user-{uuid.uuid4().hex[:8]}"
            success = db.add_user(user_id, email, password_hash, is_admin=False)
            
            if not success:
                flash('Registration failed. Please try again.', 'error')
                return render_template('login.html', email=email)
            
            flash('Registration successful! Please login.', 'success')
            return render_template('login.html', email=email)
        
        elif action == 'login':
            # Get user from database
            user = db.get_user_by_email(email)
            if not user:
                flash('No account found with this email. Please sign up first.', 'error')
                return render_template('login.html', email=email)
            
            # VERIFY with bcrypt (NDPR compliant)
            if not verify_password(password, user['password_hash']):
                flash('Invalid password', 'error')
                return render_template('login.html', email=email)
            
            # Login successful - update last login
            db.update_last_login(user['id'])
            
            # Store user info in session
            session['user'] = {
                'id': user['id'],
                'email': user['email'],
                'name': user['email'].split('@')[0],
                'is_admin': bool(user['is_admin'])
            }
            
            flash('Login successful!', 'success')
            
            if user['is_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
        'admin@tidescore.com': {
            'password_hash': hash_password(Config.ADMIN_PASSWORD),
            'is_admin': True,
            'name': 'Admin User'
        }
    }

# Global users dictionary
USERS = init_users()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    global USERS
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        action = request.form.get('action')  # 'login' or 'signup'
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('login.html', email=email)
        
        # Check if user exists
        user_exists = email in USERS
        
        if action == 'signup':
            if user_exists:
                flash('Email already registered. Please login instead.', 'error')
                return render_template('login.html', email=email)
            
            # Register new user
            if not password:
                flash('Password is required for registration', 'error')
                return render_template('login.html', email=email)
            
            USERS[email] = {
                'password_hash': hash_password(password),  # Hash the password
                'is_admin': False,
                'name': email.split('@')[0]
            }
            
            flash('Registration successful! Please login.', 'success')
            return render_template('login.html', email=email)
        
        elif action == 'login':
            if not user_exists:
                flash('No account found with this email. Please sign up first.', 'error')
                return render_template('login.html', email=email)
            
            if not password:
                flash('Please enter your password', 'error')
                return render_template('login.html', email=email)
            
            # Verify password - Compare hashed values
            user = USERS[email]
            entered_password_hash = hash_password(password)  # Hash the entered password
            
            print(f"DEBUG: Entered hash: {entered_password_hash}")  # Debug line
            print(f"DEBUG: Stored hash: {user['password_hash']}")   # Debug line
            
            if user['password_hash'] != entered_password_hash:
                flash('Invalid password', 'error')
                return render_template('login.html', email=email)
            
            # Login successful
            session['user'] = {
                'id': f"user-{email}",
                'email': email,
                'name': user['name'],
                'is_admin': user['is_admin']
            }
            
            flash('Login successful!', 'success')
            
            if user['is_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# Add a route to reset passwords for testing
@auth_bp.route('/reset_test_data')
def reset_test_data():
    global USERS
    USERS = init_users()
    flash('Test data reset successfully', 'success')
    return redirect(url_for('auth.login'))

