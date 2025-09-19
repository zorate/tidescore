"""Simple script to test user signup by calling Database.add_user and get_user_by_email.
Run from repo root with the same environment used by the app.
"""
import os
import sys
from datetime import datetime

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db
import uuid

def main():
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    test_email = f'testuser+{timestamp}@example.com'
    test_pass_hash = 'testhash'  # expecting add_user stores whatever hash is provided
    user_id = f"user-{uuid.uuid4().hex[:8]}"

    print('Attempting to add user:', test_email)
    success = db.add_user(user_id, test_email, test_pass_hash, is_admin=False)
    print('add_user returned:', success)

    found = db.get_user_by_email(test_email)
    print('get_user_by_email returned:', bool(found))
    if found:
        print('User _id:', found.get('_id'))
        print('User email:', found.get('email'))

if __name__ == '__main__':
    main()
