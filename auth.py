from flask import Blueprint, request, redirect, url_for, session, render_template, flash, jsonify
from supabase import create_client, Client
from config import Config
from models import db
import json
import os
import sqlite3

# Create a Blueprint for auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Set up Supabase client from config
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# Login/Signup Page - Shows a form to enter email
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        action = request.form.get('action')  # 'login' or 'signup'
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('index.html', email=email)
        
        try:
            # Check if user exists in our database
            user_exists = check_user_exists(email)
            
            if action == 'signup' and user_exists:
                flash('This email is already registered. Please login instead.', 'warning')
                return render_template('index.html', email=email)
            
            if action == 'login' and not user_exists:
                flash('No account found with this email. Please sign up first.', 'warning')
                return render_template('index.html', email=email)
            
            # Store the action in session for callback processing
            session['auth_action'] = action
            session['auth_email'] = email

                # Determine the correct base URL for the environment
            if os.environ.get('FLASK_ENV') == 'development':
                base_url = 'http://localhost:5000'
            else:
                base_url = 'https://tidescore.onrender.com'
            # --- ADD THESE LINES FOR DEBUGGING ---
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("DEBUG: Attempting to send magic link")
            print(f"DEBUG: Using base_url: {base_url}")
            print(f"DEBUG: Full redirect URL: {base_url}/auth/callback")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # --- END DEBUG LINES ---


            # Send magic link to the user's email
       try:
            # Try a more direct OTP approach
            result = supabase.auth.sign_in_with_otp({"email": email})
            print(f"DEBUG: OTP result: {result}")
       except Exception as e:
            print(f"DEBUG: OTP error: {e}")
            # Fallback to original method
            supabase.auth.sign_in_with_otp({
              "email": email,
              "options": {
                  "email_redirect_to": f'{base_url}/auth/callback'
                }
            })

        # ========== ADD DEBUGGING ==========
       print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
       print("DEBUG: Checking if auth worked")
       print(f"DEBUG: Email sent to: {email}")
       print(f"DEBUG: Redirect URL set to: {base_url}/auth/callback")
       print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
       # =====================================

            
               
            if action == 'signup':
                flash('Welcome! Check your email to complete registration.', 'info')
            else:
                flash('Check your email for the login link!', 'info')
                
            return render_template('index.html', email=email)
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'unique' in error_msg and 'constraint' in error_msg:
                flash('This email is already registered. Please login instead.', 'error')
            else:
                flash('Error: ' + str(e), 'error')
    
    return render_template('index.html')

# Check if user exists in our database
def check_user_exists(email):
    """Check if a user email exists in our applications database"""
    try:
        conn = sqlite3.connect('tidescore.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM applications WHERE user_email = ?', (email,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"Error checking user existence: {e}")
        return False

# Callback route - Supabase redirects here after user clicks the magic link
@auth_bp.route('/callback')
def callback():
    # Get the access token from the query parameters Supabase provides
    access_token = request.args.get('access_token')
    refresh_token = request.args.get('refresh_token')
    # Also check for other possible parameters Supabase might use
    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    # ========== ENHANCED DEBUGGING ==========
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("DEBUG: CALLBACK ROUTE TRIGGERED")
    print(f"DEBUG: All request args: {dict(request.args)}")
    print(f"DEBUG: Access Token present: {access_token is not None}")
    print(f"DEBUG: Refresh Token present: {refresh_token is not None}")
    print(f"DEBUG: Code present: {code is not None}")
    print(f"DEBUG: Error present: {error is not None}")
    print(f"DEBUG: Session keys: {list(session.keys())}")
    # =====================================
    
    # If there's an error from Supabase, handle it
    if error:
        print(f"DEBUG: Supabase error: {error} - {error_description}")
        flash(f'Authentication error: {error_description}', 'error')
        return redirect(url_for('auth.login'))
    
    # If we have a code parameter instead of direct tokens, we need to exchange it
    if code and not access_token:
        try:
            print(f"DEBUG: Attempting to exchange code for session: {code}")
            # Exchange the code for a session
            session_data = supabase.auth.exchange_code_for_session({'code': code})
            access_token = session_data.access_token
            refresh_token = session_data.refresh_token
            print(f"DEBUG: Code exchange successful. New access token: {access_token is not None}")
        except Exception as e:
            print(f"DEBUG: Error exchanging code: {str(e)}")
            flash('Invalid authentication code.', 'error')
            return redirect(url_for('auth.login'))
    
    if access_token:
        try:
            print("DEBUG: Attempting to get user data with access token...")
            # Get the user's session data using the token
            user_data = supabase.auth.get_user(access_token)
            user = user_data.user
            
            print(f"DEBUG: User authenticated: {user.email}")
            
            # Get the auth action from session
            action = session.get('auth_action', 'login')
            session_email = session.get('auth_email', '').lower()
            
            print(f"DEBUG: Session action: {action}")
            print(f"DEBUG: Session email: {session_email}")
            
            # Clear the auth session data
            session.pop('auth_action', None)
            session.pop('auth_email', None)
            
            # Verify email matches (security check)
            if session_email and session_email != user.email.lower():
                print("DEBUG: Email mismatch error!")
                print(f"DEBUG: Session email: {session_email}, User email: {user.email.lower()}")
                flash('Email mismatch detected. Please try again.', 'error')
                return redirect(url_for('auth.login'))
            
            # Check if this is a new user
            is_new_user = not check_user_exists(user.email)
            print(f"DEBUG: Is new user: {is_new_user}")
            
            # Additional check for signup action
            if action == 'signup' and not is_new_user:
                print("DEBUG: User already exists, forcing login")
                flash('This email is already registered. Redirecting to login.', 'warning')
                action = 'login'  # Force login instead
            
            # Store user info in the Flask session
            session['user'] = {
                'id': user.id,
                'email': user.email,
                'is_new_user': is_new_user
            }
            
            # Store tokens for future API calls
            session['access_token'] = access_token
            session['refresh_token'] = refresh_token
            
            print("DEBUG: Login successful! Session updated.")
            print(f"DEBUG: Redirecting to dashboard, is_new_user: {is_new_user}")
            
            # For new users, redirect to application form
            if is_new_user:
                flash('Welcome to TideScore! Please complete your application.', 'success')
                return redirect(url_for('new_application'))
            else:
                flash('Successfully logged in!', 'success')
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            print(f"DEBUG: ERROR in callback: {str(e)}")
            print(f"DEBUG: Error type: {type(e).__name__}")
            flash('Invalid login link: ' + str(e), 'error')
    
    print("DEBUG: No access token found or error occurred, redirecting to login")
    return redirect(url_for('auth.login'))

# API endpoint to check if email is registered (for AJAX)
@auth_bp.route('/check_email', methods=['POST'])
def check_email():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        email = data.get('email', '').strip().lower()
        if not email or '@' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        exists = check_user_exists(email)
        return jsonify({
            'exists': exists, 
            'email': email,
            'message': 'Email already registered' if exists else 'Email available'
        })
        
    except Exception as e:
        return jsonify({'error': 'Server error: ' + str(e)}), 500

# User profile route - shows user-specific data
#@auth_bp.route('/profile')
#def profile():
    #if 'user' not in session:
       # return redirect(url_for('auth.login'))
    
    #user_email = session['user']['email']
    
    # Get user's applications from database
   # user_applications = db.get_user_applications(session['user']['id'])
    #applications = [db.Application.from_db_row(row) for row in user_applications]
    
    #return render_template('profile.html', 
                         #user_email=user_email,
                         #applications=applications,
                         #is_new_user=session['user'].get('is_new_user', False))

# Logout route
@auth_bp.route('/logout')
def logout():
    # Clear Supabase session
    try:
        if 'access_token' in session:
            supabase.auth.sign_out(session['access_token'])
    except:
        pass
    
    # Clear Flask session
    session.clear()
    flash('You have been logged out.', 'info')

    return redirect(url_for('auth.login'))







