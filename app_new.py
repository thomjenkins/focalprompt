#!/usr/bin/env python3
"""
Flask web application for FocalPrompt - Refactored Version

This is the new modular structure. The old app.py is preserved as app.py.backup.
"""

import os
import sys
from flask import Flask, render_template, jsonify

# Load environment variables from .env file (for local development)
# Note: python-dotenv is optional - not needed for Vercel
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip (fine for production/Vercel)
    pass
except (PermissionError, OSError):
    # Can't read .env file (permissions or doesn't exist), skip
    pass
except Exception as e:
    # Any other error loading .env, just log and continue
    print(f"Warning: Could not load .env file: {e}", file=sys.stderr)

# Initialize Flask app first
app = Flask(__name__)

# Set secret key for sessions (before any routes)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Import CORS and enable it
try:
    from flask_cors import CORS
    CORS(app)
except ImportError as e:
    print(f"Warning: flask-cors not available: {e}", file=sys.stderr)

# Register blueprints with error handling
try:
    from routes.assessment_routes import assessment_bp
    app.register_blueprint(assessment_bp)
except Exception as e:
    print(f"Error registering assessment_bp: {e}", file=sys.stderr)

try:
    from routes.ablation_routes import ablation_bp
    app.register_blueprint(ablation_bp)
except Exception as e:
    print(f"Error registering ablation_bp: {e}", file=sys.stderr)

try:
    from routes.batch_routes import batch_bp
    app.register_blueprint(batch_bp)
except Exception as e:
    print(f"Error registering batch_bp: {e}", file=sys.stderr)

try:
    from routes.agent_routes import agent_bp
    app.register_blueprint(agent_bp)
except Exception as e:
    print(f"Error registering agent_bp: {e}", file=sys.stderr)

try:
    from routes.optimization_routes import optimization_bp
    app.register_blueprint(optimization_bp)
except Exception as e:
    print(f"Error registering optimization_bp: {e}", file=sys.stderr)

try:
    from routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
except Exception as e:
    print(f"Error registering auth_bp: {e}", file=sys.stderr)

try:
    from routes.payment_routes import payment_bp
    app.register_blueprint(payment_bp)
except Exception as e:
    print(f"Error registering payment_bp: {e}", file=sys.stderr)

try:
    from routes.usage_routes import usage_bp
    app.register_blueprint(usage_bp)
except Exception as e:
    print(f"Error registering usage_bp: {e}", file=sys.stderr)


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/login')
def login():
    """Serve login page."""
    return render_template('login.html')


@app.route('/signup')
def signup():
    """Serve signup page."""
    return render_template('signup.html')


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        database_url = (
            os.getenv('DATABASE_URL') or
            os.getenv('DATABASE_POSTGRES_URL') or
            os.getenv('DATABASE_SUPABASE_URL')
        )
        return jsonify({
            'status': 'ok',
            'api_key_set': api_key is not None and len(api_key) > 0,
            'database_configured': database_url is not None,
            'secret_key_set': os.getenv('SECRET_KEY') is not None,
            'vercel': os.getenv('VERCEL') is not None
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/test', methods=['GET'])
def test():
    """Minimal test endpoint that doesn't require any services."""
    return jsonify({
        'status': 'ok',
        'message': 'App is running',
        'python_version': __import__('sys').version
    })


if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '127.0.0.1')
    # Use waitress with 10-minute timeout for long-running ablation analysis
    serve(app, host=host, port=port, threads=4, channel_timeout=600)


