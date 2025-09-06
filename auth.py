from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from auth0.authentication import GetToken
from auth0.authentication import Users
from config import Config
import os

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        action = request.form.get('action')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('index.html', email=email)
        
        # Check if admin requires password
        is_admin = email in Config.ADMIN_EMAILS
        
        if is_admin:
            if not password:
                # First step: show password field for admin
                flash('Admin access requires password verification', 'info')
                return render_template('index.html', email=email, show_password=True, is_admin=True)
            
            # Verify admin password
            if password != Config.ADMIN_PASSWORD:
                flash('Invalid admin password', 'error')
                return render_template('index.html', email=email, show_password=True, is_admin=True)
        
        # Send magic link via Auth0 (for both users and admins)
        try:
            auth0 = GetToken(Config.AUTH0_DOMAIN)
            auth0.passwordless_start(
                client_id=Config.AUTH0_CLIENT_ID,
                connection='email',
                email=email,
                send='link',
                authParams={'scope': 'openid profile email'}
            )
            
            # Store admin status in session for callback
            if is_admin:
                session['pending_admin'] = True
                
            flash('Check your email for the login link!', 'info')
            
        except Exception as e:
            flash('Error sending login link. Please try again.', 'error')
        
        return render_template('index.html', email=email)
    
    return render_template('index.html')

@auth_bp.route('/callback')
def callback():
    code = request.args.get('code')
    
    if code:
        try:
            auth0 = GetToken(Config.AUTH0_DOMAIN)
            token = auth0.authorization_code(
                client_id=Config.AUTH0_CLIENT_ID,
                client_secret=Config.AUTH0_CLIENT_SECRET,
                code=code,
                grant_type='authorization_code',
                redirect_uri=f'https://tidescore.onrender.com/auth/callback'
            )
            
            # Get user info
            users = Users(Config.AUTH0_DOMAIN)
            user_info = users.userinfo(token['access_token'])
            user_email = user_info['email'].lower()
            
            # Check if user is admin
            is_admin = user_email in Config.ADMIN_EMAILS and session.get('pending_admin')
            
            # Store in session
            session['user'] = {
                'id': user_info['sub'],
                'email': user_email,
                'name': user_info.get('name', ''),
                'is_admin': is_admin
            }
            
            # Clean up
            session.pop('pending_admin', None)
            
            flash('Successfully logged in!', 'success')
            
            if is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            flash('Login failed. Please try again.', 'error')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(f'https://{Config.AUTH0_DOMAIN}/v2/logout?client_id={Config.AUTH0_CLIENT_ID}&returnTo=https://tidescore.onrender.com')

# Remove the check_email endpoint since we're using Auth0
