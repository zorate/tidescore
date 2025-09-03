import sqlite3
import json
from datetime import datetime
import os
from werkzeug.utils import secure_filename

class Database:
    def __init__(self, db_path='tidescore.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with required tables for verification system"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create applications table with file verification status and UNIQUE constraint
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,   --IJ ADD UNIQUE CONSTRAINT
                applicant_data TEXT NOT NULL,
                verification_status TEXT DEFAULT 'Pending',
                admin_verified_data TEXT,
                score_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP,
                verified_by TEXT,
                files_path TEXT,
                file_verification_status TEXT DEFAULT '{}'
            )
        ''')
        
        # Create verification history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                admin_email TEXT,
                action TEXT,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_application(self, user_id, user_email, applicant_data, files_path=None):
        """Add a new application submission"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO applications (user_id, user_email, applicant_data, files_path, verification_status, file_verification_status)
            VALUES (?, ?, ?, ?, 'Pending', '{}')
        ''', (user_id, user_email, json.dumps(applicant_data), files_path))
        
        conn.commit()
        app_id = cursor.lastrowid
        conn.close()
        return app_id
    
    def get_pending_applications(self):
        """Get all applications pending verification"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM applications 
            WHERE verification_status = 'Pending' 
            ORDER BY created_at DESC
        ''')
        
        applications = cursor.fetchall()
        conn.close()
        return applications
    
    def get_application_for_verification(self, app_id):
        """Get application details for verification"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        application = cursor.fetchone()
        conn.close()
        return application
    
    def update_verification(self, app_id, admin_email, verified_data, score_result, status='Verified'):
        """Update application verification status and scores"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE applications 
            SET verification_status = ?, 
                admin_verified_data = ?, 
                score_result = ?,
                verified_at = CURRENT_TIMESTAMP,
                verified_by = ?
            WHERE id = ?
        ''', (status, json.dumps(verified_data), json.dumps(score_result), admin_email, app_id))
        
        conn.commit()
        conn.close()
    
    def update_application_files(self, app_id, files_data):
        """Update application files metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE applications 
            SET files_path = ?
            WHERE id = ?
        ''', (files_data, app_id))
        
        conn.commit()
        conn.close()

    def update_verification_status_only(self, app_id, status, admin_email, notes=None):
        """Update only the verification status without score data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE applications 
            SET verification_status = ?,
                verified_at = CURRENT_TIMESTAMP,
                verified_by = ?
            WHERE id = ?
        ''', (status, admin_email, app_id))
        
        conn.commit()
        conn.close()
        
        # Add to verification history
        self.add_verification_history(
            app_id,
            admin_email,
            f'Status changed to {status}',
            notes=notes
        )
    
    def add_verification_history(self, app_id, admin_email, action, field_name=None, old_value=None, new_value=None, notes=None):
        """Add entry to verification history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO verification_history (application_id, admin_email, action, field_name, old_value, new_value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (app_id, admin_email, action, field_name, old_value, new_value, notes))
        
        conn.commit()
        conn.close()
    
    def get_verification_history(self, app_id):
        """Get verification history for an application"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM verification_history 
            WHERE application_id = ? 
            ORDER BY created_at DESC
        ''', (app_id,))
        
        history = cursor.fetchall()
        conn.close()
        return history

    # File verification methods
    def update_file_verification_status(self, app_id, file_type, status, admin_notes=None):
        """Update verification status for a specific file"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('SELECT file_verification_status FROM applications WHERE id = ?', (app_id,))
        result = cursor.fetchone()
        current_status = json.loads(result['file_verification_status']) if result and result['file_verification_status'] else {}
        
        # Update the specific file status
        old_status = current_status.get(file_type, 'Pending')
        current_status[file_type] = status
        
        # Save back to database
        cursor.execute('''
            UPDATE applications 
            SET file_verification_status = ?
            WHERE id = ?
        ''', (json.dumps(current_status), app_id))
        
        conn.commit()
        conn.close()
        
        # Add to history
        if admin_notes:
            self.add_verification_history(
                app_id, 
                'system', 
                'File Verification', 
                f'{file_type}_status',
                old_status,
                status,
                admin_notes
            )
        
        return current_status

    def get_file_verification_status(self, app_id):
        """Get file verification status for an application"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT file_verification_status FROM applications WHERE id = ?', (app_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result['file_verification_status']:
            return json.loads(result['file_verification_status'])
        return {
            'employment_proof': 'Pending',
            'airtime_proof': 'Pending',
            'bank_statement': 'Pending'
        }

    # Existing methods with updates
    def get_user_applications(self, user_id):
        """Get all applications for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM applications 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (user_id,))
        
        applications = cursor.fetchall()
        conn.close()
        return applications
    
    def get_application_by_id(self, app_id):
        """Get a specific application by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        application = cursor.fetchone()
        conn.close()
        return application

    def get_all_applications(self, limit=100):
        """Get all applications from all users"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM applications 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        applications = cursor.fetchall()
        conn.close()
        return applications
    
    def get_application_count(self):
        """Get total number of applications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM applications')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_verification_stats(self):
        """Get verification statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT verification_status, COUNT(*) 
            FROM applications 
            GROUP BY verification_status
        ''')
        
        stats = dict(cursor.fetchall())
        conn.close()
        return stats
    
    def get_average_score(self):
        """Get average TideScore across verified applications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT score_result FROM applications 
            WHERE verification_status = 'Verified' AND score_result IS NOT NULL
        ''')
        
        scores = cursor.fetchall()
        conn.close()
        
        total_score = 0
        count = 0
        
        for score_row in scores:
            try:
                score_data = json.loads(score_row[0])
                total_score += score_data.get('scaled_score', 0)
                count += 1
            except:
                continue
        
        return round(total_score / count, 2) if count > 0 else 0

    def get_risk_distribution(self):
        """Get count of applications by risk level"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT score_result FROM applications 
            WHERE verification_status = 'Verified' AND score_result IS NOT NULL
        ''')
        
        applications = cursor.fetchall()
        conn.close()
        
        distribution = {'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Unknown': 0}
        
        for app_row in applications:
            try:
                score_data = json.loads(app_row[0])
                risk_level = score_data.get('risk_level', 'Unknown')
                distribution[risk_level] += 1
            except:
                distribution['Unknown'] += 1
        
        return distribution

# Create a global database instance
db = Database()

class Application:
    """Helper class to work with application data"""
    
    def __init__(self):
        self.id = None
        self.user_id = None
        self.user_email = None
        self.applicant_data = {}
        self.verification_status = 'Pending'
        self.admin_verified_data = {}
        self.score_result = {}
        self.created_at = None
        self.verified_at = None
        self.verified_by = None
        self.files_path = None
        self.file_verification_status = '{}'
    
    @staticmethod
    def from_db_row(row):
        """Create an application object from database row"""
        if not row:
            return None
        
        app = Application()
        app.id = row['id']
        app.user_id = row['user_id']
        app.user_email = row['user_email']
        app.verification_status = row['verification_status']
        app.files_path = row['files_path']
        
        # Handle the new column that might not exist in older databases
        try:
            app.file_verification_status = row['file_verification_status']
        except (IndexError, KeyError):
            app.file_verification_status = '{}'  # Default value
        
        # Parse JSON data safely
        try:
            app.applicant_data = json.loads(row['applicant_data'])
        except (json.JSONDecodeError, TypeError):
            app.applicant_data = {}
        
        try:
            app.admin_verified_data = json.loads(row['admin_verified_data']) if row['admin_verified_data'] else {}
        except (json.JSONDecodeError, TypeError):
            app.admin_verified_data = {}
        
        try:
            app.score_result = json.loads(row['score_result']) if row['score_result'] else {}
        except (json.JSONDecodeError, TypeError):
            app.score_result = {}
        
        # Parse timestamps
        try:
            app.created_at = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            app.created_at = datetime.now()
        
        try:
            if row['verified_at']:
                app.verified_at = datetime.strptime(row['verified_at'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            app.verified_at = None
        
        app.verified_by = row['verified_by']
        
        return app
    
    def get_file_verification_status(self):
        """Get file verification status"""
        try:
            return json.loads(self.file_verification_status)
        except (json.JSONDecodeError, TypeError):
            return {
                'employment_proof': 'Pending',
                'airtime_proof': 'Pending', 
                'bank_statement': 'Pending'
            }
    
    def all_files_verified(self):
        """Check if all files are verified"""
        status = self.get_file_verification_status()
        return all(s == 'Verified' for s in status.values() if s != 'Not Provided')
    
    def any_files_rejected(self):
        """Check if any files are rejected"""
        status = self.get_file_verification_status()
        return any(s == 'Rejected' for s in status.values())
    
    def get_score_value(self):
        """Get the scaled score value"""
        return self.score_result.get('scaled_score', 0)
    
    def get_risk_level(self):
        """Get the risk level"""
        return self.score_result.get('risk_level', 'Not Scored')
    
    def get_breakdown_value(self, category):
        """Get specific breakdown value from score result"""
        if not self.score_result:
            return 0
        return self.score_result.get('breakdown', {}).get(category, 0)
    
    def get_verification_status_badge(self):
        """Get Bootstrap badge class based on verification status"""
        status = self.verification_status
        if status == 'Verified':
            return 'bg-success'
        elif status == 'Under Review':
            return 'bg-warning'
        elif status == 'Rejected':
            return 'bg-danger'
        else:
            return 'bg-secondary'
    
    def get_score_color_class(self):
        """Get CSS color class based on score"""
        score = self.get_score_value()
        if score >= 650:
            return 'text-success'
        elif score >= 450:
            return 'text-warning'
        elif score >= 250:
            return 'text-danger'
        else:
            return 'text-dark'
    
    def get_risk_badge_class(self):
        """Get Bootstrap badge class based on risk level"""
        risk_level = self.get_risk_level()
        if risk_level == 'Low':
            return 'bg-success'
        elif risk_level == 'Medium':
            return 'bg-warning'
        elif risk_level == 'High':
            return 'bg-danger'
        else:
            return 'bg-dark'
    
    def get_formatted_date(self):
        """Get formatted creation date"""
        return self.created_at.strftime('%Y-%m-%d %H:%M')
    
    def __repr__(self):
        return f'<Application {self.id} - {self.user_email} - Score: {self.get_score_value()}>'