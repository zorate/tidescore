import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    # Supabase Configuration (for file storage only)
    #SUPABASE_URL = os.environ.get("SUPABASE_URL")
    #SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    # Auth0 Configuration (for future use)
    AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")
    
    # Application Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "dev-encryption-key-change-in-production")
    
    # Admin Configuration
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeThisPassword123!")
    
    # Application Settings
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    
    # MongoDB configuration (replaced SQLAlchemy)
    MONGODB_URI = os.environ.get("MONGODB_URI")
    
    # Validation - Only require essential variables
    @classmethod
    def validate_config(cls):
        required_vars = ['SECRET_KEY', 'MONGODB_URI']  # Added MONGODB_URI as required
        missing = [var for var in required_vars if not os.environ.get(var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}. Please check your environment configuration.")

# Validate configuration
Config.validate_config()