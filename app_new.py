#!/usr/bin/env python3
"""
Flask web application for FocalPrompt - Refactored Version

This is the new modular structure. The old app.py is preserved as app.py.backup.
"""

import os
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from routes.assessment_routes import assessment_bp
from routes.ablation_routes import ablation_bp
from routes.batch_routes import batch_bp
from routes.agent_routes import agent_bp
from routes.optimization_routes import optimization_bp
from routes.auth_routes import auth_bp
from routes.payment_routes import payment_bp
from routes.usage_routes import usage_bp

app = Flask(__name__)
CORS(app)

# Set secret key for sessions
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Register blueprints
app.register_blueprint(assessment_bp)
app.register_blueprint(ablation_bp)
app.register_blueprint(batch_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(optimization_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(usage_bp)


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


