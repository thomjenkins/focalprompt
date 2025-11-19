#!/usr/bin/env python3
"""
Quick test script to verify the server is working
"""

import requests
import sys
import os

def test_server():
    base_url = "http://127.0.0.1:5000"
    
    print("Testing FocalPrompt server...")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Server is running")
            print(f"   ✓ API Key set: {data.get('api_key_set', False)}")
        else:
            print(f"   ✗ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to server. Is it running?")
        print("   → Start it with: python app.py")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 2: Main page
    print("\n2. Testing main page...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("   ✓ Main page loads successfully")
        else:
            print(f"   ✗ Main page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 3: Static files
    print("\n3. Testing static files...")
    for file in ["/static/css/style.css", "/static/js/app.js"]:
        try:
            response = requests.get(f"{base_url}{file}", timeout=5)
            if response.status_code == 200:
                print(f"   ✓ {file} loads")
            else:
                print(f"   ✗ {file} failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error loading {file}: {e}")
    
    print("\n" + "=" * 50)
    print("✓ All basic tests passed!")
    print(f"\nOpen your browser to: {base_url}")
    return True

if __name__ == "__main__":
    if not test_server():
        sys.exit(1)


