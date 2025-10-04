from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash, send_from_directory, send_file, abort
from config import Config
from models import db, Application
import json
import os
import uuid
from datetime import datetime
from datetime import timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# === FILE STORAGE CONSTANTS ===
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per file
MAX_TOTAL_SIZE = 30 * 1024 * 1024  # 30MB total per user

# === SECURITY HEADERS ===
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# === TEMPLATE FILTER ===
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

# === AUTH BLUEPRINT ===
from auth import auth_bp
app.register_blueprint(auth_bp)

# === ADMIN REQUIRED DECORATOR ===
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        if not session['user'].get('is_admin', False):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# === STORAGE MANAGEMENT FUNCTIONS ===
def cleanup_user_files(user_id):
    """Clean up old files when user exceeds storage limit"""
    try:
        user = db.get_user_by_id(user_id)
        if not user or user.get('total_storage_used', 0) <= MAX_TOTAL_SIZE:
            return True
            
        # Get user's files sorted by upload date (oldest first)
        files = user.get('files', [])
        files.sort(key=lambda x: x.get('uploaded_at', datetime.min))
        
        # Delete oldest files until under limit
        total_used = user.get('total_storage_used', 0)
        for file_info in files:
            if total_used <= MAX_TOTAL_SIZE:
                break
                
            # Delete physical file
            file_path = os.path.join('uploads', file_info['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Cleaned up file: {file_info['filename']}")
                
            # Update storage count
            total_used -= file_info['size']
            db.update_user_storage(user_id, file_info['size'], 'remove')
            
            # Remove from user's file list
            db.db.users.update_one(
                {"_id": user_id},
                {"$pull": {"files": {"filename": file_info['filename']}}}
            )
            
        return True
        
    except Exception as e:
        print(f"Error cleaning up user files: {e}")
        return False

# === SESSION PERSISTENCE ===
@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=7)  # Sessions last 7 days

# === UTILITY FUNCTION TO ENSURE UPLOAD DIRECTORY EXISTS ===
def ensure_upload_directory():
    """Ensure the uploads directory exists"""
    upload_dir = 'uploads'
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        print(f"Created upload directory: {upload_dir}")
    return upload_dir

# CALL THE FUNCTION WHEN APP STARTS
ensure_upload_directory()

# === ROUTES ===
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/')
def home():
    # Always show maintenance page, even for logged-in users (except admins)
    if 'user' in session and session['user'].get('is_admin', False):
        return redirect(url_for('admin_dashboard'))
    # Show maintenance page for everyone else
    return render_template('maintenance.html')

@app.route('/waitlist')
def waitlist_page():
    """Dedicated waitlist page"""
    return render_template('waitlist.html')

# === WAITLIST ROUTES ===
@app.route('/join-waitlist', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submissions"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'message': 'No data received. Please fill out the form.'
            })
        
        # Safely get data with defaults
        email = data.get('email', '').strip().lower() if data.get('email') else ''
        name = data.get('name', '').strip() if data.get('name') else ''
        phone = data.get('phone', '').strip() if data.get('phone') else ''
        company = data.get('company', '').strip() if data.get('company') else ''
        user_type = data.get('user_type', 'individual')
        
        print(f"Waitlist submission received: {email}, {name}, {phone}, {company}, {user_type}")
        
        # Basic validation
        if not email or '@' not in email:
            return jsonify({
                'success': False, 
                'message': 'Please enter a valid email address'
            })
        
        if not name:
            return jsonify({
                'success': False, 
                'message': 'Please enter your name'
            })
        
        # Add to waitlist
        success = db.add_waitlist_subscriber(email, name, phone, company, user_type)
        
        if success:
            print(f"Successfully added to waitlist: {email}")
            return jsonify({
                'success': True, 
                'message': 'Successfully joined the waitlist! You\'ll be among the first to know when we launch.'
            })
        else:
            print(f"Email already on waitlist: {email}")
            return jsonify({
                'success': False, 
                'message': 'This email is already on our waitlist. Thank you for your interest!'
            })
            
    except Exception as e:
        print(f"Error joining waitlist: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': 'An error occurred. Please try again.'
        })
    
@app.route('/dashboard')
def dashboard():
    """Redirect to maintenance"""
    flash('Application is currently in development mode. Please join our waitlist for updates.', 'info')
    return redirect(url_for('waitlist.html'))

@app.route('/storage-info')
def storage_info():
    """Redirect to maintenance"""
    flash('Application is currently in development mode. Please join our waitlist for updates.', 'info')
    return redirect(url_for('home'))

@app.route('/new_application')
def new_application():
    """Redirect to maintenance"""
    flash('Application submissions are temporarily disabled. Join our waitlist for launch updates.', 'info')
    return redirect(url_for('home'))

@app.route('/submit_application', methods=['POST'])
def submit_application():
    """Block application submissions"""
    return jsonify({
        'error': True,
        'message': 'Application submissions are temporarily disabled. Please join our waitlist for launch updates.'
    }), 503

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    """Block file access"""
    flash('File access is temporarily disabled during maintenance.', 'info')
    return redirect(url_for('home'))

@app.route('/debug-application/<app_id>')
def debug_application(app_id):
    """Block debug access"""
    flash('Debug access is temporarily disabled.', 'info')
    return redirect(url_for('home'))

@app.route('/calculate_score', methods=['POST'])
def calculate_score():
    """Block score calculations"""
    return jsonify({
        'error': True, 
        'message': 'Score calculations are temporarily disabled during maintenance.'
    }), 503

@app.route('/my_applications')
def my_applications():
    """Redirect to maintenance"""
    flash('Application history is temporarily unavailable. Please join our waitlist for launch updates.', 'info')
    return redirect(url_for('home'))

# === AUTH ROUTES - REDIRECT TO MAINTENANCE ===
@app.route('/auth/login', methods=['GET', 'POST'])
def login_redirect():
    """Redirect login attempts to maintenance"""
    flash('New registrations and logins are currently disabled. Please join our waitlist for launch updates.', 'info')
    return redirect(url_for('home'))

@app.route('/auth/register', methods=['GET', 'POST']) 
def register_redirect():
    """Redirect registration attempts to maintenance"""
    flash('New registrations are currently disabled. Please join our waitlist for launch updates.', 'info')
    return redirect(url_for('home'))

@app.route('/auth/forgot_password', methods=['GET', 'POST'])
def forgot_password_redirect():
    """Redirect password reset attempts to maintenance"""
    flash('Password reset is temporarily disabled during maintenance.', 'info')
    return redirect(url_for('home'))

# === ADMIN ROUTES - STILL ACCESSIBLE ===
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard with maintenance notice"""
    total_applications = db.get_application_count()
    waitlist_count = len(db.get_waitlist_subscribers())
    
    return render_template('admin_dashboard.html',
                         total_applications=total_applications,
                         waitlist_count=waitlist_count,
                         maintenance_mode=True)

@app.route('/admin/applications')
@admin_required
def admin_applications():
    """Admin applications view"""
    all_applications = db.get_all_applications(limit=100)
    return render_template('admin_applications.html', applications=all_applications)

@app.route('/admin/application/<app_id>')
@admin_required
def admin_application_detail(app_id):
    """Admin application detail view"""
    application = db.get_application_by_id(app_id)
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_applications'))
    
    return render_template('admin_application_detail.html', application=application)

@app.route('/admin/pending')
@admin_required
def admin_pending_applications():
    """Admin pending applications view"""
    pending_apps = db.get_pending_applications()
    return render_template('admin_pending.html', applications=pending_apps)

@app.route('/admin/verify/<app_id>', methods=['GET'])
@admin_required
def admin_verify_application(app_id):
    """Admin verification view"""
    application = db.get_application_for_verification(app_id)
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_pending_applications'))
    
    return render_template('admin_verify.html', application=application)

@app.route('/admin/verify_application/<app_id>', methods=['POST'])
@admin_required
def verify_application(app_id):
    """Admin verification submission"""
    try:
        overall_status = request.form.get('overall_status')
        
        employment_status = request.form.get('employment_proof_status')
        if employment_status:
            db.update_file_verification_status(
                app_id, 'employment_proof', employment_status, 
                request.form.get('employment_proof_notes')
            )
        
        airtime_status = request.form.get('airtime_proof_status')
        if airtime_status:
            db.update_file_verification_status(
                app_id, 'airtime_proof', airtime_status,
                request.form.get('airtime_proof_notes')
            )
        
        bank_status = request.form.get('bank_statement_status')
        if bank_status:
            db.update_file_verification_status(
                app_id, 'bank_statement', bank_status,
                request.form.get('bank_statement_notes')
            )
        
        verification_data = {
            'employment_verified': 'Yes' if employment_status == 'Verified' else 'No',
            'education_verified': 'Yes' if request.form.get('education_verified') == 'Verified' else 'No',
            'residency_verified': 'Yes',
            'airtime_status': 'Verified' if airtime_status == 'Verified' else 'Unverified',
            'bill_status': 'Verified',
            'bank_status': 'Verified' if bank_status == 'Verified' else 'Unverified',
            'g1_verified': 'Yes' if request.form.get('g1_verified') else 'No',
            'g2_verified': 'Yes' if request.form.get('g2_verified') else 'No',
            'g1_relationship': request.form.get('g1_relationship_confirmed', 'No'),
            'g2_relationship': request.form.get('g2_relationship_confirmed', 'No')
        }

        if overall_status == 'Verified':
            from scoring_algorithm import calculate_tidescore
            score_result = calculate_tidescore(verification_data)
            
            db.update_verification(
                app_id, 
                session['user']['email'], 
                verification_data, 
                score_result,
                'Verified'
            )
            flash('Application verified and score calculated!', 'success')
        else:
            db.update_verification_status_only(
                app_id, overall_status, session['user']['email'],
                request.form.get('verification_notes')
            )
            flash('Application status updated!', 'success')
        
    except Exception as e:
        flash(f'Error updating verification: {str(e)}', 'error')
    
    return redirect(url_for('admin_verify_application', app_id=app_id))

@app.route('/admin/view_document/<app_id>/<document_type>')
@admin_required
def admin_view_document(app_id, document_type):
    """Admin document viewing"""
    try:
        application = db.get_application_by_id(app_id)
        if not application:
            abort(404)
        
        if not application.files_path:
            abort(404)
            
        files_data = application.files_path
        
        if document_type not in files_data or not files_data[document_type]:
            abort(404)
        
        if isinstance(files_data[document_type], dict) and 'filename' in files_data[document_type]:
            file_path = files_data[document_type]['filename']
            absolute_path = os.path.join('uploads', file_path)
            
            if not os.path.exists(absolute_path):
                abort(404)
                
            return send_file(absolute_path, as_attachment=False)
        else:
            abort(404)
        
    except Exception as e:
        print(f"Error serving document: {e}")
        abort(500)

@app.route('/admin/verification-history/<app_id>')
@admin_required
def admin_verification_history(app_id):
    """Admin verification history"""
    history = db.get_verification_history(app_id)
    return render_template('admin_verification_history.html', history=history, app_id=app_id)

@app.route('/admin/waitlist')
@admin_required
def admin_waitlist():
    """Admin view of waitlist subscribers"""
    subscribers = db.get_waitlist_subscribers()
    return render_template('admin_waitlist.html', subscribers=subscribers)

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'app': 'TideScore'})

if __name__ == '__main__':
    print("Starting Tidescore server...")
    print("Database: MongoDB Atlas")
    
    if os.environ.get('FLASK_ENV') == 'development':
        print("Development login available at: http://localhost:5000/dev_login")
        print("Admin dashboard: http://localhost:5000/admin")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
