#!/usr/bin/env python3
"""
Register versioned public API paths and serve OpenAPI spec.

v1 routes are aliases to the same handlers as /api/... (analytical only; no key management).
"""

import json
import os
from flask import Blueprint, jsonify

api_v1_meta_bp = Blueprint('api_v1_meta', __name__)

_V1_OPENAPI = None


def _load_openapi():
    global _V1_OPENAPI
    if _V1_OPENAPI is not None:
        return _V1_OPENAPI
    path = os.path.join(os.path.dirname(__file__), '..', 'openapi', 'v1.json')
    path = os.path.normpath(path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            _V1_OPENAPI = json.load(f)
    except OSError:
        _V1_OPENAPI = {'error': 'OpenAPI spec not found', 'version': '1.0.0'}
    return _V1_OPENAPI


@api_v1_meta_bp.route('/api/v1', methods=['GET'])
def v1_root():
    return jsonify({
        'version': 1,
        'documentation': '/api/v1/openapi.json',
    })


@api_v1_meta_bp.route('/api/v1/openapi.json', methods=['GET'])
def v1_openapi():
    return jsonify(_load_openapi())


def register_v1_routes(app):
    """Add /api/v1/... URL rules that mirror core JSON API handlers."""
    from routes.assessment_routes import (
        assess,
        build_agent_prompt,
        detect_dynamic_foci,
        detect_foci,
        generate_output,
        rewrite_prompt,
    )
    from routes.ablation_routes import ablation_analysis

    mapping = [
        ('/api/v1/detect-foci', detect_foci, ['POST'], 'v1_detect_foci'),
        ('/api/v1/detect-dynamic-foci', detect_dynamic_foci, ['POST'], 'v1_detect_dynamic_foci'),
        ('/api/v1/assess', assess, ['POST'], 'v1_assess'),
        ('/api/v1/generate-output', generate_output, ['POST', 'GET'], 'v1_generate_output'),
        ('/api/v1/rewrite-prompt', rewrite_prompt, ['POST'], 'v1_rewrite_prompt'),
        ('/api/v1/build-agent-prompt', build_agent_prompt, ['POST'], 'v1_build_agent_prompt'),
        ('/api/v1/ablation-analysis', ablation_analysis, ['POST'], 'v1_ablation_analysis'),
    ]
    for path, view, methods, endpoint in mapping:
        app.add_url_rule(path, endpoint, view, methods=methods)

    app.register_blueprint(api_v1_meta_bp)
