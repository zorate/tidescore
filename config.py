import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    # Supabase Configuration
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
    
    # Application Settings
    DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@tidescore.com")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "ChangeThisPassword123!")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", 'sqlite:///tidescore.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Validation
    @classmethod
    def validate_config(cls):
        required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'SECRET_KEY']
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}. Please check your .env file")

# Validate configuration
Config.validate_config()