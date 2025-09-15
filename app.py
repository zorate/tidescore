from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash, send_from_directory, send_file, abort
from config import Config
from models import db, Application
import json
import os
import uuid
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# === SECURITY IMPROVEMENT: Add security headers ===
@app.after_request
def add_security_headers(response):
    """Add basic security headers to every response"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Add custom template filter for JSON parsing
@app.template_filter('from_json')
def from_json_filter(value):
    """Convert JSON string to Python object"""
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}

# Import and register auth blueprint
from auth import auth_bp
app.register_blueprint(auth_bp)

# Admin required decorator
def admin_required(f):
    """Decorator to ensure the user is an admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        if not session['user'].get('is_admin', False):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Homepage - Redirects to dashboard if logged in, else to login page
@app.route('/')
def home():
    if 'user' in session:
        if session['user'].get('is_admin', False):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))

# User Dashboard - Main page after login
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('dashboard.html', user_email=session['user']['email'])

# Page to submit a new credit application
@app.route('/new_application')
def new_application():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('applications.html')

# New route to handle application submissions with LOCAL file uploads
@app.route('/submit_application', methods=['POST'])
def submit_application():
    if 'user' not in session:
        return jsonify({'error': 'Not authorized'}), 401

    try:
        # Get form data
        applicant_data = {
            'full_name': request.form.get('full_name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'dob': request.form.get('dob'),
            'employment_status': request.form.get('employment_status'),
            'employer_name': request.form.get('employer_name'),
            'monthly_income': request.form.get('monthly_income'),
            'airtime_spend_m1': request.form.get('airtime_spend_m1'),
            'airtime_spend_m2': request.form.get('airtime_spend_m2'),
            'airtime_spend_m3': request.form.get('airtime_spend_m3'),
            'bank_name': request.form.get('bank_name'),
            'account_number': request.form.get('account_number'),
            'avg_monthly_balance': request.form.get('avg_monthly_balance'),
            'g1_name': request.form.get('g1_name'),
            'g1_phone': request.form.get('g1_phone'),
            'g2_name': request.form.get('g2_name'),
            'g2_phone': request.form.get('g2_phone')
        }

        # === LOCAL FILE UPLOAD (no Supabase) ===
        files_uploaded = {}
        for file_type in ['employment_proof', 'airtime_proof', 'bank_statement']:
            if file_type in request.files:
                file = request.files[file_type]
                if file and file.filename:
                    # Security check - only allow certain file types
                    allowed_extensions = ['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx']
                    file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    
                    if file_extension in allowed_extensions:
                        try:
                            # Generate unique filename
                            unique_filename = f"{session['user']['id']}_{file_type}_{uuid.uuid4().hex}.{file_extension}"
                            
                            # Create uploads directory if it doesn't exist
                            upload_dir = 'uploads'
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Save file locally
                            file_path = os.path.join(upload_dir, unique_filename)
                            file.save(file_path)
                            
                            files_uploaded[file_type] = {
                                'path': unique_filename,  # Store filename only
                                'verified': False,
                                'verification_notes': '',
                                'verified_by': '',
                                'verified_at': ''
                            }
                            
                            print(f"File saved locally: {file_path}")
                            
                        except Exception as e:
                            print(f"Error saving file {file.filename}: {e}")
                            flash(f'Error uploading {file_type}: {str(e)}', 'error')
                    else:
                        print(f"Rejected invalid file type: {file.filename}")
                        flash(f'Invalid file type for {file_type}. Allowed: PDF, PNG, JPG, JPEG, DOC, DOCX', 'error')

        # Save application to database (without score yet - waiting for verification)
        app_id = db.add_application(
            session['user']['id'],
            session['user']['email'],
            applicant_data,
            json.dumps(files_uploaded) if files_uploaded else None  # Store as JSON string
        )

        # Store the application ID in session for score calculation later
        session['last_application_id'] = app_id
        print(f"Application {app_id} submitted successfully! Waiting for verification.")

        return jsonify({
            'success': True,
            'message': 'Application submitted successfully! It will be reviewed by our team.',
            'application_id': app_id
        })

    except Exception as e:
        print("Error submitting application:", e)
        return jsonify({'error': 'Failed to submit application'}), 500

# Add this route to serve uploaded files
@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory('uploads', filename)

# API Endpoint to calculate the score (UPDATED - updates existing application)
@app.route('/calculate_score', methods=['POST'])
def calculate_score():
    if 'user' not in session:
        return jsonify({'error': 'Not authorized'}), 401

    try:
        # Get JSON data sent from the frontend
        applicant_data = request.get_json()
        print("Received data:", applicant_data)

        # Calculate the score using our algorithm
        from scoring_algorithm import calculate_tidescore
        score_result = calculate_tidescore(applicant_data)
        print("Score calculated:", score_result)

        # Get the application ID from session (set during form submission)
        app_id = session.get('last_application_id')
        if not app_id:
            return jsonify({'error': 'No application found to update with score'}), 400

        # Update the existing application with the score result
        # First, get the current application data
        app_row = db.get_application_by_id(app_id)
        if not app_row:
            return jsonify({'error': 'Application not found'}), 404

        # Merge the score result with existing applicant data
        application = Application.from_db_row(app_row)
        current_data = application.applicant_data
        
        if isinstance(current_data, str):
            try:
                current_data = json.loads(current_data)
            except:
                current_data = {}
        
        # Add score to the data
        current_data['score_result'] = score_result
        
        # Update the application in database with the score
        conn = sqlite3.connect('tidescore.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE applications SET applicant_data = ?, score_result = ? WHERE id = ?",
            (json.dumps(current_data), json.dumps(score_result), app_id)
        )
        conn.commit()
        conn.close()

        print(f"Score added to application {app_id}")

        return jsonify(score_result)

    except Exception as e:
        print("Error calculating score:", e)
        return jsonify({'error': 'Failed to calculate score'}), 500

# Route to view application history
@app.route('/my_applications')
def my_applications():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    db_applications = db.get_user_applications(session['user']['id'])
    applications = [Application.from_db_row(row) for row in db_applications]
    
    return render_template('application_history.html', applications=applications)

# ADMIN ROUTES
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get admin statistics
    total_applications = db.get_application_count()
    average_score = db.get_average_score()
    risk_distribution = db.get_risk_distribution()
    recent_applications = db.get_all_applications(limit=10)
    verification_stats = db.get_verification_stats()
    
    applications = [Application.from_db_row(row) for row in recent_applications]
    
    return render_template('admin_dashboard.html',
                         total_applications=total_applications,
                         average_score=average_score,
                         risk_distribution=risk_distribution,
                         verification_stats=verification_stats,
                         applications=applications)

@app.route('/admin/applications')
@admin_required
def admin_applications():
    all_applications = db.get_all_applications(limit=100)
    applications = [Application.from_db_row(row) for row in all_applications]
    
    return render_template('admin_applications.html', applications=applications)

@app.route('/admin/application/<int:app_id>')
@admin_required
def admin_application_detail(app_id):
    app_row = db.get_application_by_id(app_id)
    if not app_row:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_applications'))
    
    application = Application.from_db_row(app_row)
    
    return render_template('admin_application_detail.html', application=application)

# NEW VERIFICATION ROUTES
@app.route('/admin/pending')
@admin_required
def admin_pending_applications():
    pending_apps = db.get_pending_applications()
    applications = [Application.from_db_row(row) for row in pending_apps]
    
    return render_template('admin_pending.html', applications=applications)

@app.route('/admin/verify/<int:app_id>', methods=['GET'])
@admin_required
def admin_verify_application(app_id):
    app_row = db.get_application_for_verification(app_id)
    if not app_row:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_pending_applications'))
    
    application = Application.from_db_row(app_row)
    
    return render_template('admin_verify.html', application=application)

@app.route('/admin/verify_application/<int:app_id>', methods=['POST'])
@admin_required
def verify_application(app_id):
    """Handle application verification with file checks"""
    try:
        # Get form data
        overall_status = request.form.get('overall_status')
        
        # Update individual file statuses
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
        
        # Update overall application status
        db.update_verification_status_only(
            app_id, overall_status, session['user']['email'],
            request.form.get('verification_notes')
        )
        
        flash('Application verification updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating verification: {str(e)}', 'error')
    
    return redirect(url_for('admin_verify_application', app_id=app_id))

@app.route('/admin/view_document/<int:app_id>/<document_type>')
@admin_required
def admin_view_document(app_id, document_type):
    """Secure route for admins to view applicant documents"""
    try:
        # Get the application
        app_row = db.get_application_by_id(app_id)
        if not app_row:
            abort(404)
        
        application = Application.from_db_row(app_row)
        
        # Parse the file paths
        if not application.files_path:
            abort(404)
            
        files_data = json.loads(application.files_path)
        
        # Check if the requested document type exists
        if document_type not in files_data or not files_data[document_type]:
            abort(404)
        
        # For LOCAL file storage
        if isinstance(files_data[document_type], dict) and 'path' in files_data[document_type]:
            file_path = files_data[document_type]['path']
            absolute_path = os.path.join('uploads', file_path)
            
            if not os.path.exists(absolute_path):
                abort(404)
                
            return send_file(absolute_path, as_attachment=False)
        else:
            abort(404)
        
    except Exception as e:
        print(f"Error serving document: {e}")
        abort(500)

@app.route('/admin/verification-history/<int:app_id>')
@admin_required
def admin_verification_history(app_id):
    history = db.get_verification_history(app_id)
    return render_template('admin_verification_history.html', history=history, app_id=app_id)

# Secure development login - only accessible in development mode
@app.route('/dev_login', methods=['GET', 'POST'])
def dev_login():
    # ONLY allow in development environment
    if os.environ.get('FLASK_ENV') != 'development':
        flash('Development login is disabled in production', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'user')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('dev_login.html', email=email)
        
        # Set up user session based on role
        session['user'] = {
            'id': f'dev-user-{uuid.uuid4().hex[:8]}',
            'email': email,
            'name': email.split('@')[0],
            'is_admin': role == 'admin'
        }
        
        flash(f'Development login successful as {email} ({role})', 'success')
        
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template('dev_login.html')

# For Vercel deployment
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Health check endpoint for deployment
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'app': 'TideScore'})

# Add this at the very end of app.py
if __name__ == '__main__':
    print("Starting Tidescore server...")
    print("Database: tidescore.db (SQLite)")
    
    # Only show dev login info in development
    if os.environ.get('FLASK_ENV') == 'development':
        print("Development login available at: http://localhost:5000/dev_login")
        print("Admin dashboard: http://localhost:5000/admin")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)