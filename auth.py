from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from config import Config
from models import db
import bcrypt
import uuid
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pymongo.errors import DuplicateKeyError

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# PROPER password hashing for NDPR compliance
def hash_password(password):
    """Hash password using bcrypt with salt - NDPR compliant"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password, hashed_password):
    """Verify password against bcrypt hash - NDPR compliant"""
    try:
        # Ensure both are bytes
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode()
        return bcrypt.checkpw(plain_password.encode(), hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def send_password_reset_email(email, reset_token):
    """Send password reset email (simplified version)"""
    # In production, you would integrate with a real email service
    # For now, we'll just log the token
    reset_url = f"https://tidescore.onrender.com/auth/reset-password/{reset_token}"
    print(f"Password reset for {email}: {reset_url}")
    
    # TODO: Implement actual email sending with SMTP or email service
    # For now, we'll flash a message with the token for testing
    flash(f'Password reset link: {reset_url}', 'info')
    return True

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to appropriate dashboard
    if 'user' in session:
        if session['user'].get('is_admin', False):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        action = request.form.get('action')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return redirect(url_for('home'))  # Redirect to home page which has the beautiful design
        
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return redirect(url_for('home'))  # Redirect to home page
        
        if action == 'signup':
            try:
                # Check if user already exists
                existing_user = db.get_user_by_email(email)
                if existing_user:
                    flash('Email already registered. Please login instead.', 'error')
                    return redirect(url_for('home'))
                
                # Hash password with bcrypt (NDPR compliant)
                password_hash = hash_password(password)
                print(f"DEBUG: Generated password hash: {password_hash[:30]}...")
                
                # Register new user
                user_id = f"user-{uuid.uuid4().hex[:8]}"
                success = db.add_user(user_id, email, password_hash, is_admin=False)
                
                if not success:
                    flash('Registration failed. Please try again.', 'error')
                    return redirect(url_for('home'))
                
                # DOUBLE CHECK: Verify user was actually stored
                verify_user = db.get_user_by_email(email)
                if not verify_user:
                    flash('Registration completed but user not found. Please contact support.', 'error')
                    return redirect(url_for('home'))
                
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('home'))
                
            except DuplicateKeyError:
                flash('Email already registered. Please login instead.', 'error')
                return redirect(url_for('home'))
            except Exception as e:
                print(f"Registration error: {e}")
                flash('Registration failed due to system error. Please try again.', 'error')
                return redirect(url_for('home'))
        
        elif action == 'login':
            try:
                # Get user from database
                user = db.get_user_by_email(email)
                if not user:
                    flash('No account found with this email. Please sign up first.', 'error')
                    return redirect(url_for('home'))
                
                # VERIFY with bcrypt (NDPR compliant)
                if not verify_password(password, user['password_hash']):
                    flash('Invalid password', 'error')
                    return redirect(url_for('home'))
                
                # Login successful - update last login
                db.update_last_login(user['_id'])
                
                # Store user info in session
                session['user'] = {
                    'id': user['_id'],
                    'email': user['email'],
                    'name': user['email'].split('@')[0],
                    'is_admin': bool(user.get('is_admin', False))
                }
                
                flash('Login successful!', 'success')
                
                if user.get('is_admin', False):
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
                    
            except Exception as e:
                print(f"Login error: {e}")
                flash('Login failed. Please try again.', 'error')
                return redirect(url_for('home'))
    
    # For GET requests, redirect to home page which shows the beautiful index.html
    return redirect(url_for('home'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('forgot_password.html')
        
        # Check if user exists
        user = db.get_user_by_email(email)
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            token_expiry = datetime.utcnow() + timedelta(hours=1)
            
            # Save token to database
            if db.set_password_reset_token(email, reset_token, token_expiry):
                # Send reset email
                if send_password_reset_email(email, reset_token):
                    flash('Password reset instructions have been sent to your email.', 'success')
                else:
                    flash('Failed to send email. Please try again.', 'error')
            else:
                flash('Failed to process reset request. Please try again.', 'error')
        else:
            # Don't reveal whether email exists for security
            flash('If this email is registered, you will receive reset instructions shortly.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Verify token is valid and not expired
    user = db.get_user_by_reset_token(token)
    
    if not user:
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or len(new_password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('reset_password.html', token=token)
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        
        # Update password
        new_password_hash = hash_password(new_password)
        if db.update_user_password(user['_id'], new_password_hash):
            flash('Password reset successfully! Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Failed to reset password. Please try again.', 'error')
    
    return render_template('reset_password.html', token=token)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))  # Redirect to home page instead of login page