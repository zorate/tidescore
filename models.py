from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from datetime import datetime
import bcrypt
import os
from config import Config
import json

# MongoDB connection
try:
    client = MongoClient(Config.MONGODB_URI)
    mongo_db = client.get_database()
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    mongo_db = None

class Database:
    def __init__(self):
        self.db = mongo_db
        self.init_db()
    
    def init_db(self):
        """Initialize database collections and indexes"""
        if self.db is None:
            print("Database connection is None, skipping initialization")
            return
            
        try:
            # Create indexes
            self.db.users.create_index([("email", ASCENDING)], unique=True)
            self.db.applications.create_index([("user_id", ASCENDING)])
            self.db.applications.create_index([("user_email", ASCENDING)])
            self.db.applications.create_index([("verification_status", ASCENDING)])
            self.db.verification_history.create_index([("application_id", ASCENDING)])
            
            # Create admin user if it doesn't exist
            admin_email = "admin@tidescore.com"
            admin_password = os.environ.get('ADMIN_PASSWORD', 'ChangeThisPassword123!')
            
            if not self.get_user_by_email(admin_email):
                password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
                self.add_user("admin-user", admin_email, password_hash, True)
                print("Admin user created successfully!")
                
        except Exception as e:
            print(f"Error during database initialization: {e}")

    # ===== USER METHODS =====
    def add_user(self, user_id, email, password_hash, is_admin=False):
        """Add a new user to the database"""
        if self.db is None:
            print("Database connection is None, cannot add user")
            return False
            
        try:
            user_data = {
                "_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "is_admin": is_admin,
                "created_at": datetime.utcnow(),
                "last_login": None
            }
            result = self.db.users.insert_one(user_data)
            return result.inserted_id is not None
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user_by_email(self, email):
        """Get user by email address"""
        if self.db is None:
            print("Database connection is None, cannot get user")
            return None
            
        try:
            return self.db.users.find_one({"email": email})
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def verify_user_password(self, email, password):
        """Verify user password using bcrypt"""
        user = self.get_user_by_email(email)
        if user:
            return bcrypt.checkpw(password.encode(), user['password_hash'].encode())
        return False
    
    def update_last_login(self, user_id):
        """Update user's last login timestamp"""
        if self.db is None:
            print("Database connection is None, cannot update last login")
            return False
            
        try:
            self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            return True
        except Exception as e:
            print(f"Error updating last login: {e}")
            return False

    # ===== APPLICATION METHODS =====
    def add_application(self, user_id, user_email, applicant_data, files_path=None):
        """Add a new application submission"""
        if self.db is None:
            print("Database connection is None, cannot add application")
            return None
            
        try:
            application_data = {
                "user_id": user_id,
                "user_email": user_email,
                "applicant_data": applicant_data,
                "files_path": files_path,
                "verification_status": "Pending",
                "file_verification_status": {},
                "created_at": datetime.utcnow(),
                "verified_at": None,
                "verified_by": None,
                "admin_verified_data": None,
                "score_result": None
            }
            result = self.db.applications.insert_one(application_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error adding application: {e}")
            return None
    
    def get_pending_applications(self):
        """Get all applications pending verification"""
        if self.db is None:
            print("Database connection is None, cannot get pending applications")
            return []
            
        try:
            applications = self.db.applications.find(
                {"verification_status": "Pending"}
            ).sort("created_at", DESCENDING)
            return [Application.from_dict(app) for app in applications]
        except Exception as e:
            print(f"Error getting pending applications: {e}")
            return []
    
    def get_application_for_verification(self, app_id):
        """Get application details for verification"""
        if self.db is None:
            print("Database connection is None, cannot get application for verification")
            return None
            
        try:
            application = self.db.applications.find_one({"_id": ObjectId(app_id)})
            return Application.from_dict(application) if application else None
        except Exception as e:
            print(f"Error getting application for verification: {e}")
            return None
    
    def update_verification(self, app_id, admin_email, verified_data, score_result, status='Verified'):
        """Update application verification status and scores"""
        if self.db is None:
            print("Database connection is None, cannot update verification")
            return False
            
        try:
            self.db.applications.update_one(
                {"_id": ObjectId(app_id)},
                {"$set": {
                    "verification_status": status,
                    "admin_verified_data": verified_data,
                    "score_result": score_result,
                    "verified_at": datetime.utcnow(),
                    "verified_by": admin_email
                }}
            )
            return True
        except Exception as e:
            print(f"Error updating verification: {e}")
            return False
    
    def update_verification_status_only(self, app_id, status, admin_email, notes=None):
        """Update only the verification status without score data"""
        if self.db is None:
            print("Database connection is None, cannot update verification status")
            return False
            
        try:
            self.db.applications.update_one(
                {"_id": ObjectId(app_id)},
                {"$set": {
                    "verification_status": status,
                    "verified_at": datetime.utcnow(),
                    "verified_by": admin_email
                }}
            )
            
            # Add to verification history
            self.add_verification_history(
                app_id,
                admin_email,
                f'Status changed to {status}',
                notes=notes
            )
            return True
        except Exception as e:
            print(f"Error updating verification status: {e}")
            return False
    
    def add_verification_history(self, app_id, admin_email, action, field_name=None, old_value=None, new_value=None, notes=None):
        """Add entry to verification history"""
        if self.db is None:
            print("Database connection is None, cannot add verification history")
            return False
            
        try:
            history_data = {
                "application_id": ObjectId(app_id),
                "admin_email": admin_email,
                "action": action,
                "field_name": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "notes": notes,
                "created_at": datetime.utcnow()
            }
            self.db.verification_history.insert_one(history_data)
            return True
        except Exception as e:
            print(f"Error adding verification history: {e}")
            return False
    
    def get_verification_history(self, app_id):
        """Get verification history for an application"""
        if self.db is None:
            print("Database connection is None, cannot get verification history")
            return []
            
        try:
            history = self.db.verification_history.find(
                {"application_id": ObjectId(app_id)}
            ).sort("created_at", DESCENDING)
            return list(history)
        except Exception as e:
            print(f"Error getting verification history: {e}")
            return []
    
    def update_file_verification_status(self, app_id, file_type, status, admin_notes=None):
        """Update verification status for a specific file"""
        if self.db is None:
            print("Database connection is None, cannot update file verification status")
            return {}
            
        try:
            # Get current status
            application = self.db.applications.find_one({"_id": ObjectId(app_id)})
            if not application:
                return {}
                
            current_status = application.get('file_verification_status', {})
            
            # Update the specific file status
            old_status = current_status.get(file_type, 'Pending')
            current_status[file_type] = status
            
            # Save back to database
            self.db.applications.update_one(
                {"_id": ObjectId(app_id)},
                {"$set": {"file_verification_status": current_status}}
            )
            
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
        except Exception as e:
            print(f"Error updating file verification status: {e}")
            return {}
    
    def get_user_applications(self, user_id):
        """Get all applications for a user"""
        if self.db is None:
            print("Database connection is None, cannot get user applications")
            return []
            
        try:
            applications = self.db.applications.find(
                {"user_id": user_id}
            ).sort("created_at", DESCENDING)
            return [Application.from_dict(app) for app in applications]
        except Exception as e:
            print(f"Error getting user applications: {e}")
            return []
    
    def get_application_by_id(self, app_id):
        """Get a specific application by ID"""
        if self.db is None:
            print("Database connection is None, cannot get application by ID")
            return None
            
        try:
            application = self.db.applications.find_one({"_id": ObjectId(app_id)})
            return Application.from_dict(application) if application else None
        except Exception as e:
            print(f"Error getting application by ID: {e}")
            return None
    
    def get_all_applications(self, limit=100):
        """Get all applications from all users"""
        if self.db is None:
            print("Database connection is None, cannot get all applications")
            return []
            
        try:
            applications = self.db.applications.find().sort("created_at", DESCENDING).limit(limit)
            return [Application.from_dict(app) for app in applications]
        except Exception as e:
            print(f"Error getting all applications: {e}")
            return []
    
    def get_application_count(self):
        """Get total number of applications"""
        if self.db is None:
            print("Database connection is None, cannot get application count")
            return 0
            
        try:
            return self.db.applications.count_documents({})
        except Exception as e:
            print(f"Error getting application count: {e}")
            return 0
    
    def get_verification_stats(self):
        """Get verification statistics"""
        if self.db is None:
            print("Database connection is None, cannot get verification stats")
            return {}
            
        try:
            pipeline = [
                {"$group": {
                    "_id": "$verification_status",
                    "count": {"$sum": 1}
                }}
            ]
            results = list(self.db.applications.aggregate(pipeline))
            return {result["_id"]: result["count"] for result in results}
        except Exception as e:
            print(f"Error getting verification stats: {e}")
            return {}
    
    def get_average_score(self):
        """Get average TideScore across verified applications"""
        if self.db is None:
            print("Database connection is None, cannot get average score")
            return 0
            
        try:
            pipeline = [
                {"$match": {
                    "verification_status": "Verified",
                    "score_result.scaled_score": {"$exists": True}
                }},
                {"$group": {
                    "_id": None,
                    "avg_score": {"$avg": "$score_result.scaled_score"}
                }}
            ]
            result = list(self.db.applications.aggregate(pipeline))
            return round(result[0]["avg_score"], 2) if result else 0
        except Exception as e:
            print(f"Error getting average score: {e}")
            return 0
    
    def get_risk_distribution(self):
        """Get count of applications by risk level"""
        if self.db is None:
            print("Database connection is None, cannot get risk distribution")
            return {'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Unknown': 0}
            
        try:
            pipeline = [
                {"$match": {
                    "verification_status": "Verified",
                    "score_result.risk_level": {"$exists": True}
                }},
                {"$group": {
                    "_id": "$score_result.risk_level",
                    "count": {"$sum": 1}
                }}
            ]
            results = list(self.db.applications.aggregate(pipeline))
            
            distribution = {'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Unknown': 0}
            for result in results:
                distribution[result["_id"]] = result["count"]
            
            return distribution
        except Exception as e:
            print(f"Error getting risk distribution: {e}")
            return {'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Unknown': 0}
    
    def update_application_score(self, app_id, score_result):
        """Update application with score result"""
        if self.db is None:
            print("Database connection is None, cannot update application score")
            return False
            
        try:
            self.db.applications.update_one(
                {"_id": ObjectId(app_id)},
                {"$set": {"score_result": score_result}}
            )
            return True
        except Exception as e:
            print(f"Error updating application score: {e}")
            return False

# Create a global database instance
db = Database()

# ==================== APPLICATION CLASS ====================
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
        self.file_verification_status = {}
    
    def get_score_dict(self):
        """Safely get score_result whether it's a dict or not"""
        if isinstance(self.score_result, dict):
            return self.score_result
        return {}
    
    def get_score_value(self):
        """Get the scaled score value"""
        return self.get_score_dict().get('scaled_score', 0)
    
    def get_risk_level(self):
        """Get the risk level"""
        return self.get_score_dict().get('risk_level', 'Not Scored')
    
    def get_breakdown_value(self, category):
        """Get specific breakdown value from score result"""
        score_dict = self.get_score_dict()
        if not score_dict:
            return 0
        return score_dict.get('breakdown', {}).get(category, 0)
    
    @staticmethod
    def from_dict(data):
        """Create an application object from MongoDB document"""
        if not data:
            return None
        
        app = Application()
        app.id = str(data.get("_id", ""))
        app.user_id = data.get("user_id", "")
        app.user_email = data.get("user_email", "")
        app.verification_status = data.get("verification_status", "Pending")
        app.files_path = data.get("files_path", {})
        app.file_verification_status = data.get("file_verification_status", {})
        app.applicant_data = data.get("applicant_data", {})
        app.admin_verified_data = data.get("admin_verified_data", {})
        app.score_result = data.get("score_result", {})
        app.created_at = data.get("created_at")
        app.verified_at = data.get("verified_at")
        app.verified_by = data.get("verified_by")
        
        return app
    
    def get_file_verification_status(self):
        """Get file verification status"""
        return self.file_verification_status
    
    def all_files_verified(self):
        """Check if all files are verified"""
        status = self.get_file_verification_status()
        return all(s == 'Verified' for s in status.values() if s != 'Not Provided')
    
    def any_files_rejected(self):
        """Check if any files are rejected"""
        status = self.get_file_verification_status()
        return any(s == 'Rejected' for s in status.values())
    
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
        if self.created_at:
            return self.created_at.strftime('%Y-%m-%d %H:%M')
        return "Unknown"
    
    def __repr__(self):
        return f'<Application {self.id} - {self.user_email} - Score: {self.get_score_value()}>'