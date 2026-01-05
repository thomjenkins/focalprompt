#!/usr/bin/env python3
"""
Vercel serverless function entry point.

This is the entry point for Vercel's serverless functions.
"""

import sys
import os

# Add error handling for imports
try:
    from app_new import app
    
    # Export the app for Vercel
    handler = app
    print("✅ App imported successfully", file=sys.stderr)
except Exception as e:
    # If app fails to import, create a minimal error handler
    from flask import Flask, jsonify
    
    error_app = Flask(__name__)
    
    @error_app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'message': str(e),
            'type': type(e).__name__,
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    @error_app.route('/api/test', methods=['GET'])
    def test():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'message': str(e),
            'type': type(e).__name__
        }), 500
    
    @error_app.route('/<path:path>')
    @error_app.route('/')
    def error_handler(path=''):
        return jsonify({
            'error': 'Application initialization failed',
            'message': str(e),
            'type': type(e).__name__,
            'path': path,
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    handler = error_app
    
    # Also print to stderr for Vercel logs
    print(f"❌ ERROR: Failed to import app: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

