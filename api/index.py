#!/usr/bin/env python3
"""
Vercel serverless function entry point.

This is the entry point for Vercel's serverless functions.
"""

import sys
import os
import traceback

# Add detailed logging
def log_error(message, exception=None):
    """Log error to stderr with full details."""
    print(f"❌ {message}", file=sys.stderr)
    if exception:
        print(f"Exception type: {type(exception).__name__}", file=sys.stderr)
        print(f"Exception message: {str(exception)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    # Also log environment info
    print(f"Python version: {sys.version}", file=sys.stderr)
    print(f"Working directory: {os.getcwd()}", file=sys.stderr)
    print(f"VERCEL env: {os.getenv('VERCEL')}", file=sys.stderr)
    print(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'Not set')}", file=sys.stderr)

# Try to import app with detailed error handling
try:
    print("🔄 Attempting to import app_new...", file=sys.stderr)
    from app_new import app
    print("✅ App imported successfully", file=sys.stderr)
    handler = app
except ImportError as e:
    log_error("ImportError: Failed to import app_new", e)
    # Create error handler
    from flask import Flask, jsonify
    error_app = Flask(__name__)
    
    @error_app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': 'ImportError',
            'message': str(e),
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    @error_app.route('/api/test', methods=['GET'])
    def test():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': 'ImportError',
            'message': str(e)
        }), 500
    
    @error_app.route('/<path:path>')
    @error_app.route('/')
    def error_handler(path=''):
        return jsonify({
            'error': 'Application initialization failed',
            'error_type': 'ImportError',
            'message': str(e),
            'path': path,
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    handler = error_app
except Exception as e:
    log_error("Unexpected error importing app", e)
    # Create error handler
    from flask import Flask, jsonify
    error_app = Flask(__name__)
    
    @error_app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e),
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    @error_app.route('/api/test', methods=['GET'])
    def test():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e)
        }), 500
    
    @error_app.route('/<path:path>')
    @error_app.route('/')
    def error_handler(path=''):
        return jsonify({
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e),
            'path': path,
            'note': 'Check Vercel function logs for full traceback'
        }), 500
    
    handler = error_app

