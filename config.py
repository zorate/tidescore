import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Supabase Configuration
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
    
    # Auth0 Configuration
    AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")
    
    # Admin Configuration
    ADMIN_EMAILS = [email.strip() for email in os.environ.get("ADMIN_EMAILS", "").split(",") if email.strip()]
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    
    # Application Settings
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", 'sqlite:///tidescore.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Validation
    @classmethod
    def validate_config(cls):
        required_vars = ['SECRET_KEY', 'AUTH0_DOMAIN', 'AUTH0_CLIENT_ID', 'AUTH0_CLIENT_SECRET']
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

Config.validate_config()
