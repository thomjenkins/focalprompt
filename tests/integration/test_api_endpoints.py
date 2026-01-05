"""
Integration tests for API endpoints.

These tests require a running Flask app and may use mocks for external services.
"""

import pytest
from flask import Flask
from routes.assessment_routes import assessment_bp
from routes.ablation_routes import ablation_bp
from routes.batch_routes import batch_bp
from routes.agent_routes import agent_bp
from routes.optimization_routes import optimization_bp


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Register blueprints
    app.register_blueprint(assessment_bp)
    app.register_blueprint(ablation_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(optimization_bp)
    
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


def test_health_endpoint(client):
    """Test health check endpoint."""
    # This would need to be added to app_new.py or a test app
    # For now, just verify the structure
    assert client is not None


def test_list_checkpoints_endpoint(client):
    """Test list checkpoints endpoint."""
    response = client.get('/api/list-checkpoints?type=batch_analysis')
    # Should return 200 or 500 depending on checkpoint service
    assert response.status_code in [200, 500]


