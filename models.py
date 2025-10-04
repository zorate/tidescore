from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from datetime import datetime
import bcrypt
import os
from config import Config
import json
import time
from pymongo.errors import DuplicateKeyError

def _connect_with_retry(uri, max_retries=3, base_delay=2):
    """Attempt to connect to MongoDB with retries and a ping health check."""
    if not uri:
        print("❌ MONGODB_URI is not set. Please set the MONGODB_URI environment variable.")
        return None, None

    from urllib.parse import urlparse
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempting to connect to MongoDB (attempt {attempt})...")
            client = MongoClient(uri, serverSelectionTimeoutMS=10000)

            # Use a lightweight ping to validate connectivity/auth
            client.admin.command('ping')
            print("✅ Successfully connected to MongoDB!")

            # Parse DB name from URI path (if present)
            parsed_uri = urlparse(uri)
            db_name = parsed_uri.path[1:] if parsed_uri.path else ''
            db_name = db_name.split('?')[0] if db_name else ''
            if not db_name:
                db_name = 'tidescore'
                print("No database name found in URI; defaulting to 'tidescore'")

            db = client[db_name]
            print(f"Using database: {db_name}")
            return client, db

        except Exception as e:
            last_exc = e
            print(f"❌ MongoDB connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                print(f"Retrying in {delay}s...")
                time.sleep(delay)

    print("❌ All MongoDB connection attempts failed.")
    print("Possible causes: wrong URI, network restrictions, paused cluster, or bad credentials.")
    print("Tips: verify MONGODB_URI, allow your IP in Atlas Network Access, and ensure the user has proper DB privileges.")
    print(f"Last error: {last_exc}")
    return None, None

# MongoDB connection
client, mongo_db = _connect_with_retry(Config.MONGODB_URI, max_retries=3, base_delay=2)

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
            # Create collections by inserting empty documents if they don't exist
            collections_to_create = ['users', 'applications', 'verification_history', 'waitlist'] #ADD 'WAITLIST' TO CREATE IT'S COLLECION
            
            for collection_name in collections_to_create:
                if collection_name not in self.db.list_collection_names():
                    print(f"Creating collection: {collection_name}")
                    self.db[collection_name].insert_one({'_init': True, 'created_at': datetime.utcnow()})
                    self.db[collection_name].delete_one({'_init': True})
            
            # Create indexes
            self.db.users.create_index([("email", ASCENDING)], unique=True)
            self.db.applications.create_index([("user_id", ASCENDING)])
            self.db.applications.create_index([("user_email", ASCENDING)])
            self.db.applications.create_index([("verification_status", ASCENDING)])
            self.db.verification_history.create_index([("application_id", ASCENDING)])
            self.db.waitlist.create_index([("email", ASCENDING)], unique=True)  # ADD THIS LINE FOR WAITLIST
            
            # Ensure admin user exists (idempotent upsert to avoid duplicate-key logs)
            admin_email = "admin@tidescore.com"
            admin_password = os.environ.get('ADMIN_PASSWORD', 'ChangeThisPassword123!')

            try:
                password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
                admin_doc = {
                    "_id": "admin-user",
                    "email": admin_email,
                    "password_hash": password_hash,
                    "is_admin": True,
                    "created_at": datetime.utcnow(),
                    "last_login": None,
                    "reset_token": None,
                    "reset_token_expiry": None,
                    "total_storage_used": 0,
                    "files": []
                }

                # Use $setOnInsert so existing admin is preserved and no duplicate-key error is raised
                result = self.db.users.update_one(
                    {"_id": admin_doc["_id"]},
                    {"$setOnInsert": admin_doc},
                    upsert=True
                )

                if result.upserted_id:
                    print("Admin user created successfully (upsert)")
                else:
                    print("Admin user already exists (no-op)")
            except Exception as e:
                print(f"Error ensuring admin user exists: {e}")
                
            # Initialize storage fields for existing users
            self.initialize_storage_fields()
                
        except Exception as e:
            print(f"Error during database initialization: {e}")

    # ===== STORAGE MANAGEMENT METHODS =====
    def get_user_storage_info(self, user_id):
        """Get storage information for a specific user"""
        if self.db is None:
            print("Database connection is None, cannot get storage info")
            return None
            
        try:
            user = self.db.users.find_one({"_id": user_id})
            if not user:
                return None
            
            used = user.get('total_storage_used', 0)
            limit = 30 * 1024 * 1024  # 30MB limit
            
            return {
                'used': used,
                'limit': limit,
                'available': max(0, limit - used),
                'file_count': len(user.get('files', []))
            }
        except Exception as e:
            print(f"Error getting user storage info: {e}")
            return None

    def update_user_storage(self, user_id, size, operation='add'):
        """Update user's storage usage"""
        if self.db is None:
            print("Database connection is None, cannot update storage")
            return False
            
        try:
            if operation == 'add':
                update_op = {"$inc": {"total_storage_used": size}}
            else:  # remove
                update_op = {"$inc": {"total_storage_used": -size}}
            
            result = self.db.users.update_one({"_id": user_id}, update_op)
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating user storage: {e}")
            return False

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        if self.db is None:
            print("Database connection is None, cannot get user by ID")
            return None
            
        try:
            return self.db.users.find_one({"_id": user_id})
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None

    def get_user_files(self, user_id):
        """Get all files for a user"""
        if self.db is None:
            print("Database connection is None, cannot get user files")
            return []
            
        try:
            user = self.db.users.find_one({"_id": user_id})
            return user.get('files', []) if user else []
        except Exception as e:
            print(f"Error getting user files: {e}")
            return []

    def initialize_storage_fields(self):
        """Initialize storage fields for existing users who don't have them"""
        if self.db is None:
            print("Database connection is None, cannot initialize storage fields")
            return False
            
        try:
            # Update users who don't have total_storage_used field
            result1 = self.db.users.update_many(
                {"total_storage_used": {"$exists": False}},
                {"$set": {"total_storage_used": 0}}
            )
            
            # Update users who don't have files field
            result2 = self.db.users.update_many(
                {"files": {"$exists": False}},
                {"$set": {"files": []}}
            )
            
            print(f"Initialized storage fields for {result1.modified_count + result2.modified_count} users")
            return True
        except Exception as e:
            print(f"Error initializing storage fields: {e}")
            return False
            
    def add_waitlist_subscriber(self, email, name=None, phone=None, company=None, user_type='individual'):
        """Add a new subscriber to the waitlist"""
        if self.db is None:
            print("Database connection is None, cannot add waitlist subscriber")
            return False
        
        try:
            subscriber_data = {
                "email": email,
                "name": name,
                "phone": phone,
                "company": company,
                "user_type": user_type,
                "subscribed_at": datetime.utcnow(),
                "status": "active"
            }
        
            # Check if email already exists
            existing = self.db.waitlist.find_one({"email": email})
        if existing:
            return False
            
            result = self.db.waitlist.insert_one(subscriber_data)
            return result.inserted_id is not None
        
        except Exception as e:
            print(f"Error adding waitlist subscriber: {e}")
        return False

    def get_waitlist_subscribers(self):
        """Get all waitlist subscribers"""
        if self.db is None:
            print("Database connection is None, cannot get waitlist subscribers")
        return []
        
        try:
            subscribers = self.db.waitlist.find({"status": "active"}).sort("subscribed_at", DESCENDING)
        return list(subscribers)
        except Exception as e:
            print(f"Error getting waitlist subscribers: {e}")
        return []
        
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
                "last_login": None,
                "reset_token": None,
                "reset_token_expiry": None,
                "total_storage_used": 0,
                "files": []
            }
            print(f"DEBUG: Attempting to insert user: { {k: v for k, v in user_data.items() if k != 'password_hash'} }")
            
            result = self.db.users.insert_one(user_data)
            
            if result.inserted_id:
                print(f"DEBUG: User inserted successfully with ID: {result.inserted_id}")
                # Verify the user was actually stored
                verify_user = self.db.users.find_one({"_id": user_id})
                if verify_user:
                    print(f"DEBUG: Verification - User found in DB: {verify_user['_id']}")
                else:
                    print("DEBUG: Verification FAILED - User not found after insertion!")
                return True
            else:
                print("DEBUG: User insertion failed - no inserted_id returned")
                return False
                
        except DuplicateKeyError:
            print(f"User with email {email} already exists")
            return False
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user_by_email(self, email):
        """Get user by email address"""
        if self.db is None:
            print("Database connection is None, cannot get user")
            return None
            
        try:
            print(f"DEBUG: Searching for user with email: {email}")
            user = self.db.users.find_one({"email": email})
            if user:
                print(f"DEBUG: User found: {user['_id']}")
                print(f"DEBUG: User data: { {k: v for k, v in user.items() if k != 'password_hash'} }")
            else:
                print("DEBUG: No user found with this email")
            return user
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    def verify_user_password(self, email, password):
        """Verify user password using bcrypt"""
        user = self.get_user_by_email(email)
        if user:
            print(f"DEBUG: Verifying password for user: {user['_id']}")
            print(f"DEBUG: Stored hash: {user['password_hash'][:20]}...")
            
            # Check if password_hash is a string or bytes
            if isinstance(user['password_hash'], bytes):
                stored_hash = user['password_hash']
            else:
                stored_hash = user['password_hash'].encode()
                
            result = bcrypt.checkpw(password.encode(), stored_hash)
            print(f"DEBUG: Password verification result: {result}")
            return result
        print("DEBUG: No user found for password verification")
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

    # ===== PASSWORD RESET METHODS =====
    def set_password_reset_token(self, email, token, expiry):
        """Set password reset token for a user"""
        if self.db is None:
            print("Database connection is None, cannot set reset token")
            return False
            
        try:
            self.db.users.update_one(
                {"email": email},
                {"$set": {
                    "reset_token": token,
                    "reset_token_expiry": expiry
                }}
            )
            return True
        except Exception as e:
            print(f"Error setting reset token: {e}")
            return False
    
    def get_user_by_reset_token(self, token):
        """Get user by reset token"""
        if self.db is None:
            print("Database connection is None, cannot get user by token")
            return None
            
        try:
            return self.db.users.find_one({
                "reset_token": token,
                "reset_token_expiry": {"$gt": datetime.utcnow()}
            })
        except Exception as e:
            print(f"Error getting user by token: {e}")
            return None
    
    def update_user_password(self, user_id, new_password_hash):
        """Update user password and clear reset token"""
        if self.db is None:
            print("Database connection is None, cannot update password")
            return False
            
        try:
            self.db.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "password_hash": new_password_hash,
                    "reset_token": None,
                    "reset_token_expiry": None
                }}
            )
            return True
        except Exception as e:
            print(f"Error updating password: {e}")
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
