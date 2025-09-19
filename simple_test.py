# verify_connection.py
import subprocess
import sys

# Install pymongo if not already installed
subprocess.check_call([sys.executable, "-m", "pip", "install", "pymongo"])

from pymongo import MongoClient

# Test with the exact same code your app uses
uri = "mongodb+srv://zoratejoseph_db_user:bRfz6IJLOi18rTNd@cluster0.x7thbot.mongodb.net/tidescore?retryWrites=true&w=majority&appName=Cluster0"

print("Testing with the exact same connection string your app uses...")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    
    # Try a different approach to test connection
    info = client.server_info()
    print(f"✅ Connected to MongoDB version {info.get('version', 'unknown')}")
    
    # Try to list databases
    dbs = client.list_database_names()
    print(f"Available databases: {dbs}")
    
except Exception as e:
    print(f"❌ Final test failed: {e}")
    print("\nThis suggests the issue is with:")
    print("1. Your MongoDB user doesn't exist or has wrong permissions")
    print("2. Your cluster is paused or not accessible")
    print("3. Network restrictions are blocking the connection")
    print("\nPlease check these in MongoDB Atlas:")
    print("- Database Access: User exists with correct privileges")
    print("- Network Access: IP 0.0.0.0/0 is allowed")
    print("- Cluster Status: Cluster is active and running")