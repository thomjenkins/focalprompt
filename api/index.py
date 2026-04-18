#!/usr/bin/env python3
"""
Vercel serverless function entry point.

Vercel's @vercel/python builder statically scans this file for a top-level name
`app`, `application`, or `handler`. Assignments only inside `try:` may not count,
so we MUST end with `app = build_app()` at module level.
"""

import sys
import os
import traceback


def log_error(message, exception=None):
    """Log error to stderr with full details."""
    print(f"❌ {message}", file=sys.stderr)
    if exception:
        print(f"Exception type: {type(exception).__name__}", file=sys.stderr)
        print(f"Exception message: {str(exception)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    print(f"Python version: {sys.version}", file=sys.stderr)
    print(f"Working directory: {os.getcwd()}", file=sys.stderr)


def build_app():
    """Import and configure the Flask app, or return a minimal error app."""
    try:
        print("🔄 Attempting to import app_new...", file=sys.stderr)
        from app_new import app as flask_app
        print("✅ App imported successfully", file=sys.stderr)
        print(f"App type: {type(flask_app)}", file=sys.stderr)

        print("📋 Registered routes:", file=sys.stderr)
        api_routes = [r for r in flask_app.url_map.iter_rules() if str(r).startswith('/api/')]
        print(f"   Total API routes: {len(api_routes)}", file=sys.stderr)
        for route in sorted(api_routes, key=lambda x: str(x))[:30]:
            print(f"   {list(route.methods)} {route}", file=sys.stderr)

        generate_output_routes = [r for r in flask_app.url_map.iter_rules() if '/api/generate-output' in str(r)]
        print(f"🔍 generate-output routes: {len(generate_output_routes)}", file=sys.stderr)
        for route in generate_output_routes:
            print(f"   ✅ {list(route.methods)} {route} (endpoint: {route.endpoint})", file=sys.stderr)

        assessment_routes = [r for r in flask_app.url_map.iter_rules() if 'assessment' in r.endpoint]
        print(f"🔍 assessment blueprint routes: {len(assessment_routes)}", file=sys.stderr)
        if len(assessment_routes) == 0:
            print("   ⚠️ WARNING: No assessment routes found! Attempting manual registration...", file=sys.stderr)
            try:
                print("   🔄 Step 1: Importing assessment_routes module...", file=sys.stderr)
                import routes.assessment_routes as assessment_module
                print("   ✅ Module imported", file=sys.stderr)
                assessment_bp = assessment_module.assessment_bp
                print(f"   ✅ Blueprint retrieved: {assessment_bp.name}", file=sys.stderr)
                bp_routes = list(assessment_bp.deferred_functions)
                print(f"   ✅ Blueprint has {len(bp_routes)} routes", file=sys.stderr)
                print("   🔄 Step 4: Registering blueprint with app...", file=sys.stderr)
                flask_app.register_blueprint(assessment_bp)
                print("   ✅ Blueprint registered", file=sys.stderr)
                assessment_routes_after = [r for r in flask_app.url_map.iter_rules() if 'assessment' in r.endpoint]
                print(f"   ✅ Verification: {len(assessment_routes_after)} assessment routes now registered", file=sys.stderr)
                for route in assessment_routes_after[:10]:
                    print(f"      - {list(route.methods)} {route}", file=sys.stderr)
            except ImportError as e:
                print(f"   ❌ ImportError: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            except AttributeError as e:
                print(f"   ❌ AttributeError: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            except Exception as e:
                print(f"   ❌ Unexpected error ({type(e).__name__}): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

        def _ensure_assessment_bp_registered():
            assessment_routes = [r for r in flask_app.url_map.iter_rules() if 'assessment' in r.endpoint]
            if len(assessment_routes) == 0:
                try:
                    print("🔄 FORCE REGISTERING assessment_bp...", file=sys.stderr)
                    import routes.assessment_routes
                    flask_app.register_blueprint(routes.assessment_routes.assessment_bp)
                    print("✅ assessment_bp force-registered successfully", file=sys.stderr)
                except Exception as e:
                    print(f"❌ Failed to force-register assessment_bp: {type(e).__name__}: {e}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

        _ensure_assessment_bp_registered()

        def _ensure_agent_bp_registered():
            agent_routes = [r for r in flask_app.url_map.iter_rules() if 'agent' in r.endpoint]
            if len(agent_routes) == 0:
                try:
                    print("🔄 FORCE REGISTERING agent_bp...", file=sys.stderr)
                    import routes.agent_routes
                    flask_app.register_blueprint(routes.agent_routes.agent_bp)
                    print("✅ agent_bp force-registered successfully", file=sys.stderr)
                except Exception as e:
                    print(f"❌ Failed to force-register agent_bp: {type(e).__name__}: {e}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

        _ensure_agent_bp_registered()

        from flask import jsonify as flask_jsonify

        @flask_app.route('/api/diagnostic', methods=['GET'])
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

        return flask_app

    except Exception as e:
        log_error("Failed to import app_new", e)
        from flask import Flask, jsonify
        err_app = Flask(__name__)

        @err_app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'error',
                'error': 'Application initialization failed',
                'error_type': type(e).__name__,
                'message': str(e),
                'note': 'Check Vercel Runtime Logs for full traceback'
            }), 500

        @err_app.route('/api/test', methods=['GET'])
        def test():
            return jsonify({
                'status': 'error',
                'error': 'Application initialization failed',
                'error_type': type(e).__name__,
                'message': str(e),
                'note': 'Check Vercel Runtime Logs for full traceback'
            }), 500

        @err_app.route('/api/diagnostic', methods=['GET'])
        def diagnostic_err():
            return jsonify({
                'status': 'error',
                'app_imported': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'python_version': sys.version,
                'working_dir': os.getcwd(),
                'note': 'This error occurred during app import. Check Vercel Runtime Logs for full traceback.'
            }), 500

        @err_app.route('/<path:path>')
        @err_app.route('/')
        def error_handler(path=''):
            return jsonify({
                'error': 'Application initialization failed',
                'error_type': type(e).__name__,
                'message': str(e),
                'path': path,
                'note': 'Check Vercel Runtime Logs for full traceback'
            }), 500

        return err_app


# Required by @vercel/python: a top-level binding named `app` (not only inside try/except).
app = build_app()
# Some tooling also looks for `application`
application = app
