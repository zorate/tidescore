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

# === ROUTES ===
@app.route('/')
def home():
    if 'user' in session:
        if session['user'].get('is_admin', False):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('dashboard.html', user_email=session['user']['email'])

@app.route('/new_application')
def new_application():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('applications.html')

@app.route('/submit_application', methods=['POST'])
def submit_application():
    if 'user' not in session:
        return jsonify({'error': 'Not authorized'}), 401

    try:
        applicant_data = {
            'full_name': request.form.get('full_name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'dob': request.form.get('dob'),
            'education_level': request.form.get('education_level'),
            'employment_status': request.form.get('employment_status'),
            'employer_name': request.form.get('employer_name'),
            'monthly_income': request.form.get('monthly_income'),
            'airtime_spend_m1': request.form.get('airtime_spend_m1'),
            'airtime_spend_m2': request.form.get('airtime_spend_m2'),
            'airtime_spend_m3': request.form.get('airtime_spend_m3'),
            'bank_name': request.form.get('bank_name'),
            'account_number': request.form.get('account_number'),
            'avg_monthly_balance': request.form.get('avg_monthly_balance'),
            'electricity_verified': 'Yes' if request.form.get('electricity_verified') else 'No',
            'dstv_verified': 'Yes' if request.form.get('dstv_verified') else 'No',
            'internet_verified': 'Yes' if request.form.get('internet_verified') else 'No',
            'water_verified': 'Yes' if request.form.get('water_verified') else 'No',
            'rent_verified': 'Yes' if request.form.get('rent_verified') else 'No',
            'g1_name': request.form.get('g1_name'),
            'g1_phone': request.form.get('g1_phone'),
            'g1_relationship': request.form.get('g1_relationship'),
            'g2_name': request.form.get('g2_name'),
            'g2_phone': request.form.get('g2_phone'),
            'g2_relationship': request.form.get('g2_relationship')
        }

        files_uploaded = {}
        for file_type in ['employment_proof', 'airtime_proof', 'bank_statement']:
            if file_type in request.files:
                file = request.files[file_type]
                if file and file.filename:
                    allowed_extensions = ['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx']
                    file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    
                    if file_extension in allowed_extensions:
                        try:
                            unique_filename = f"{session['user']['id']}_{file_type}_{uuid.uuid4().hex}.{file_extension}"
                            upload_dir = 'uploads'
                            os.makedirs(upload_dir, exist_ok=True)
                            file_path = os.path.join(upload_dir, unique_filename)
                            file.save(file_path)
                            
                            files_uploaded[file_type] = {
                                'path': unique_filename,
                                'verified': False,
                                'verification_notes': '',
                                'verified_by': '',
                                'verified_at': ''
                            }
                            
                        except Exception as e:
                            print(f"Error saving file {file.filename}: {e}")
                            flash(f'Error uploading {file_type}: {str(e)}', 'error')
                    else:
                        flash(f'Invalid file type for {file_type}. Allowed: PDF, PNG, JPG, JPEG, DOC, DOCX', 'error')

        app_id = db.add_application(
            session['user']['id'],
            session['user']['email'],
            applicant_data,
            files_uploaded if files_uploaded else None
        )

        session['last_application_id'] = app_id
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully! It will be reviewed by our team.',
            'application_id': app_id
        })

    except Exception as e:
        print("Error submitting application:", e)
        return jsonify({'error': 'Failed to submit application'}), 500

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/calculate_score', methods=['POST'])
def calculate_score():
    if 'user' not in session:
        return jsonify({'error': 'Not authorized'}), 401

    try:
        applicant_data = request.get_json()
        from scoring_algorithm import calculate_tidescore
        score_result = calculate_tidescore(applicant_data)

        app_id = session.get('last_application_id')
        if not app_id:
            return jsonify({'error': 'No application found to update with score'}), 400

        application = db.get_application_by_id(app_id)
        if not application:
            return jsonify({'error': 'Application not found'}), 404

        # Update application with score result
        db.update_application_score(app_id, score_result)

        return jsonify(score_result)

    except Exception as e:
        print("Error calculating score:", e)
        return jsonify({'error': 'Failed to calculate score'}), 500

@app.route('/my_applications')
def my_applications():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    applications = db.get_user_applications(session['user']['id'])
    return render_template('application_history.html', applications=applications)

# === ADMIN ROUTES ===
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_applications = db.get_application_count()
    average_score = db.get_average_score()
    risk_distribution = db.get_risk_distribution()
    recent_applications = db.get_all_applications(limit=10)
    verification_stats = db.get_verification_stats()
    
    return render_template('admin_dashboard.html',
                         total_applications=total_applications,
                         average_score=average_score,
                         risk_distribution=risk_distribution,
                         verification_stats=verification_stats,
                         applications=recent_applications)

@app.route('/admin/applications')
@admin_required
def admin_applications():
    all_applications = db.get_all_applications(limit=100)
    return render_template('admin_applications.html', applications=all_applications)

@app.route('/admin/application/<app_id>')
@admin_required
def admin_application_detail(app_id):
    application = db.get_application_by_id(app_id)
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_applications'))
    
    return render_template('admin_application_detail.html', application=application)

@app.route('/admin/pending')
@admin_required
def admin_pending_applications():
    pending_apps = db.get_pending_applications()
    return render_template('admin_pending.html', applications=pending_apps)

@app.route('/admin/verify/<app_id>', methods=['GET'])
@admin_required
def admin_verify_application(app_id):
    application = db.get_application_for_verification(app_id)
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('admin_pending_applications'))
    
    return render_template('admin_verify.html', application=application)

@app.route('/admin/verify_application/<app_id>', methods=['POST'])
@admin_required
def verify_application(app_id):
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
    try:
        application = db.get_application_by_id(app_id)
        if not application:
            abort(404)
        
        if not application.files_path:
            abort(404)
            
        files_data = application.files_path
        
        if document_type not in files_data or not files_data[document_type]:
            abort(404)
        
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

@app.route('/admin/verification-history/<app_id>')
@admin_required
def admin_verification_history(app_id):
    history = db.get_verification_history(app_id)
    return render_template('admin_verification_history.html', history=history, app_id=app_id)

@app.route('/dev_login', methods=['GET', 'POST'])
def dev_login():
    if os.environ.get('FLASK_ENV') != 'development':
        flash('Development login is disabled in production', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'user')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('dev_login.html', email=email)
        
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