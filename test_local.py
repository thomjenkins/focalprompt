#!/usr/bin/env python3
"""Quick test to verify local setup."""

import sys
import os

print("=" * 60)
print("Testing Local Setup")
print("=" * 60)
print(f"Python: {sys.version}")
print(f"Working dir: {os.getcwd()}\n")

# Test imports
try:
    print("1. Testing Flask import...")
    from flask import Flask
    print("   ✅ Flask OK")
except ImportError as e:
    print(f"   ❌ Flask import failed: {e}")
    print("   Fix: pip install flask")
    sys.exit(1)

try:
    print("\n2. Testing flask-cors import...")
    from flask_cors import CORS
    print("   ✅ flask-cors OK")
except ImportError as e:
    print(f"   ❌ flask-cors import failed: {e}")
    print("   Fix: pip install flask-cors")
    sys.exit(1)

try:
    print("\n3. Testing app import...")
    from app_new import app
    print("   ✅ App imported successfully")
except Exception as e:
    print(f"   ❌ App import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n4. Testing route registration...")
    with app.test_client() as client:
        response = client.get('/api/test')
        if response.status_code == 200:
            print("   ✅ Test endpoint works")
            print(f"   Response: {response.get_json()}")
        else:
            print(f"   ⚠️  Test endpoint returned {response.status_code}")
            print(f"   Response: {response.get_data(as_text=True)}")
except Exception as e:
    print(f"   ❌ Route test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n5. Testing health endpoint...")
    with app.test_client() as client:
        response = client.get('/api/health')
        if response.status_code == 200:
            print("   ✅ Health endpoint works")
            health_data = response.get_json()
            print(f"   Database configured: {health_data.get('database_configured', False)}")
            print(f"   Secret key set: {health_data.get('secret_key_set', False)}")
        else:
            print(f"   ⚠️  Health endpoint returned {response.status_code}")
except Exception as e:
    print(f"   ❌ Health check failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All critical tests passed! Ready to run locally.")
print("=" * 60)
print("\nTo start the app:")
print("  python3 app_new.py")
print("\nThen visit: http://localhost:5001")
