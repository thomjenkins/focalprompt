#!/usr/bin/env python3
"""
Vercel serverless function entry point.

Vercel expects a Flask app instance to be exported as 'app'.
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
    print(f"Python version: {sys.version}", file=sys.stderr)
    print(f"Working directory: {os.getcwd()}", file=sys.stderr)

# Try to import app - Vercel expects 'app' to be a Flask instance
try:
    print("🔄 Attempting to import app_new...", file=sys.stderr)
    from app_new import app
    print("✅ App imported successfully", file=sys.stderr)
    print(f"App type: {type(app)}", file=sys.stderr)
    
    # Log all registered routes for debugging
    print("📋 Registered routes:", file=sys.stderr)
    api_routes = [r for r in app.url_map.iter_rules() if str(r).startswith('/api/')]
    print(f"   Total API routes: {len(api_routes)}", file=sys.stderr)
    for route in sorted(api_routes, key=lambda x: str(x))[:30]:  # First 30
        print(f"   {list(route.methods)} {route}", file=sys.stderr)
    
    # Specifically check for generate-output
    generate_output_routes = [r for r in app.url_map.iter_rules() if '/api/generate-output' in str(r)]
    print(f"🔍 generate-output routes: {len(generate_output_routes)}", file=sys.stderr)
    for route in generate_output_routes:
        print(f"   ✅ {list(route.methods)} {route} (endpoint: {route.endpoint})", file=sys.stderr)
    
    # Check for assessment blueprint routes
    assessment_routes = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
    print(f"🔍 assessment blueprint routes: {len(assessment_routes)}", file=sys.stderr)
    if len(assessment_routes) == 0:
        print("   ⚠️ WARNING: No assessment routes found! Blueprint may not have registered.", file=sys.stderr)
        # Try to import and see what happens
        try:
            print("   🔄 Attempting to manually import assessment_bp...", file=sys.stderr)
            from routes.assessment_routes import assessment_bp
            print(f"   ✅ assessment_bp imported: {assessment_bp.name}, routes: {len(list(assessment_bp.deferred_functions))}", file=sys.stderr)
            print("   🔄 Attempting to register manually...", file=sys.stderr)
            app.register_blueprint(assessment_bp)
            print("   ✅ Manual registration successful", file=sys.stderr)
            # Check again
            assessment_routes_after = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
            print(f"   ✅ assessment routes after manual registration: {len(assessment_routes_after)}", file=sys.stderr)
        except Exception as e:
            print(f"   ❌ Manual import/registration failed: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    # Add a diagnostic endpoint
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
    
    # Vercel expects 'app' to be the Flask instance - it's already set from the import
    
except Exception as e:
    log_error("Failed to import app_new", e)
    # Create a minimal error app - Vercel expects 'app' to be defined
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e),
            'note': 'Check Vercel Runtime Logs for full traceback'
        }), 500
    
    @app.route('/api/test', methods=['GET'])
    def test():
        return jsonify({
            'status': 'error',
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e),
            'note': 'Check Vercel Runtime Logs for full traceback'
        }), 500
    
    @app.route('/api/diagnostic', methods=['GET'])
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
    
    @app.route('/<path:path>')
    @app.route('/')
    def error_handler(path=''):
        return jsonify({
            'error': 'Application initialization failed',
            'error_type': type(e).__name__,
            'message': str(e),
            'path': path,
            'note': 'Check Vercel Runtime Logs for full traceback'
        }), 500

# Vercel's Python handler expects 'app' to be a Flask instance
# It will automatically detect and use it
