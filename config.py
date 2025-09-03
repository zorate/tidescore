# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    
    # Database configuration - SIMPLE SQLite
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tidescore.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    if not all([SUPABASE_URL, SUPABASE_KEY, SECRET_KEY]):
        raise ValueError("Missing required environment variables. Please check your .env file")