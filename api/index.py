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
    
    # Add a diagnostic endpoint that shows import status
    from flask import jsonify as flask_jsonify
    @app.route('/api/diagnostic', methods=['GET'])
    def diagnostic():
        """Diagnostic endpoint to check app status."""
        import importlib
        modules_status = {}
        try:
            importlib.import_module('flask')
            modules_status['flask'] = 'OK'
        except Exception as e:
            modules_status['flask'] = f'ERROR: {e}'
        
        try:
            importlib.import_module('flask_cors')
            modules_status['flask_cors'] = 'OK'
        except Exception as e:
            modules_status['flask_cors'] = f'ERROR: {e}'
        
        return flask_jsonify({
            'status': 'ok',
            'app_imported': True,
            'modules': modules_status,
            'python_version': sys.version,
            'working_dir': os.getcwd(),
            'vercel': os.getenv('VERCEL') is not None
        })
    
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
            'message': str(e),
            'note': 'Check Vercel Runtime Logs for full traceback. Go to: Deployment → Runtime Logs'
        }), 500
    
    @error_app.route('/api/diagnostic', methods=['GET'])
    def diagnostic():
        """Diagnostic endpoint that shows the import error."""
        return jsonify({
            'status': 'error',
            'app_imported': False,
            'error_type': 'ImportError',
            'error_message': str(e),
            'python_version': sys.version,
            'working_dir': os.getcwd(),
            'note': 'This error occurred during app import. Check Vercel Runtime Logs for full traceback.'
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
            'message': str(e),
            'note': 'Check Vercel Runtime Logs for full traceback. Go to: Deployment → Runtime Logs'
        }), 500
    
    @error_app.route('/api/diagnostic', methods=['GET'])
    def diagnostic():
        """Diagnostic endpoint that shows the import error."""
        return jsonify({
            'status': 'error',
            'app_imported': False,
            'error_type': type(e).__name__,
            'error_message': str(e),
            'python_version': sys.version,
            'working_dir': os.getcwd(),
            'note': 'This error occurred during app import. Check Vercel Runtime Logs for full traceback.'
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

