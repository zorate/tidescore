"""verify_connection.py

Small helper to validate MongoDB connection string and print actionable diagnostics.

Usage (PowerShell):
$env:MONGODB_URI = '<your uri>' ; python .\verify_connection.py
Or:
python .\verify_connection.py 'mongodb+srv://user:pass@cluster0...'

This script performs a ping and prints server_info on success. On failure it prints
common causes and checks (URI formatting, URL-encoding password, Atlas IP whitelist, user privileges).
"""
import os
import sys
import traceback
from pymongo import MongoClient

# If python-dotenv is available, load .env so MONGODB_URI set there is visible
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Informative message (harmless) — helps users know .env was loaded
    if os.path.exists('.env'):
        print("Loaded environment from .env")
except Exception:
    # dotenv not installed or failed to load — continue, env may be set externally
    pass


def diagnose(uri):
    if not uri:
        print("❌ No MONGODB_URI provided. Set the MONGODB_URI environment variable or pass it as the first argument.")
        return 2

    print(f"Testing MongoDB URI: {uri[:60]}{'...' if len(uri) > 60 else ''}")

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        # lightweight ping
        info = client.admin.command('ping')
        print("✅ Ping succeeded:", info)

        # print server version
        server_info = client.server_info()
        print(f"MongoDB server version: {server_info.get('version')}")

        # Try listing databases (may require privileges)
        try:
            dbs = client.list_database_names()
            print(f"Available databases (first 10): {dbs[:10]}")
        except Exception as e:
            print(f"Could not list databases: {e}")

        return 0

    except Exception as e:
        print("❌ Connection failed:")
        tb = traceback.format_exc()
        print(tb)

        # Common causes and checks
        print("Possible causes and checks:")
        print("  - Invalid username or password. Ensure the user exists in MongoDB Atlas and the password is correct.")
        print("  - URL-encode special characters in the password (e.g., @, :, /). Use urllib.parse.quote_plus for encoding.)")
        print("  - The connection string's database name may be missing or different than expected. Example: mongodb+srv://user:pass@.../tidescore?...")
        print("  - Atlas Network Access: add your client IP to the whitelist (or 0.0.0.0/0 for testing).")
        print("  - The user might not have privileges to run the operations attempted (e.g., list databases). Check user roles.")
        print("  - If using SCRAM or other auth mechanisms, ensure the URI includes correct options.")
        print("  - For special characters in the connection string, prefer using mongodb+srv for SRV records if provided by Atlas.")

        # Helpful hint: show how to URL-encode a password
        try:
            from urllib.parse import quote_plus
            sample_password = 'p@ss/w:ord'
            print('\nExample encoding:')
            print(f"  raw: {sample_password}")
            print(f"  encoded: {quote_plus(sample_password)}")
        except Exception:
            pass

        return 1


if __name__ == '__main__':
    uri = None
    if len(sys.argv) > 1:
        uri = sys.argv[1]
    else:
        uri = os.environ.get('MONGODB_URI')

    rc = diagnose(uri)
    sys.exit(rc)
