#!/usr/bin/env python3
"""
Flask web application for Focal Prompt — research toolkit UI + optional hosted demo.
"""

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from utils.experiment_config import EXPERIMENT_COPY
from utils.hosted_mode import (
    allow_live_inference,
    check_live_allowed,
    is_hosted_mode,
    path_requires_live,
)
from utils.results_copy import COPY

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
    print("🔄 Attempting to import assessment_bp...", file=sys.stderr)
    from routes.assessment_routes import assessment_bp
    print("✅ assessment_bp imported successfully", file=sys.stderr)
    print(f"   Blueprint name: {assessment_bp.name}", file=sys.stderr)
    print(f"   Blueprint routes before registration: {len(list(assessment_bp.deferred_functions))}", file=sys.stderr)
    
    app.register_blueprint(assessment_bp)
    print("✅ assessment_bp registered with app", file=sys.stderr)
    
    # Count actual routes registered
    assessment_routes = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
    print(f"✅ Registered assessment_bp with {len(assessment_routes)} routes", file=sys.stderr)
    for route in assessment_routes:
        print(f"   - {list(route.methods)} {route}", file=sys.stderr)
except ImportError as e:
    print(f"❌ ImportError registering assessment_bp: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
except Exception as e:
    print(f"❌ Error registering assessment_bp: {type(e).__name__}: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

try:
    from routes.ablation_routes import ablation_bp
    app.register_blueprint(ablation_bp)
except Exception as e:
    print(f"Error registering ablation_bp: {e}", file=sys.stderr)

try:
    from routes.behavioral_difference_routes import behavioral_difference_bp
    app.register_blueprint(behavioral_difference_bp)
except Exception as e:
    print(f"Error registering behavioral_difference_bp: {e}", file=sys.stderr)

try:
    from routes.batch_routes import batch_bp
    app.register_blueprint(batch_bp)
    batch_routes = [r for r in app.url_map.iter_rules() if 'batch' in r.endpoint]
    print(f"✅ Registered batch_bp with {len(batch_routes)} routes", file=sys.stderr)
    for route in batch_routes:
        print(f"   - {list(route.methods)} {route}", file=sys.stderr)
except Exception as e:
    print(f"❌ Error registering batch_bp: {type(e).__name__}: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

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
    from routes.pricing_routes import pricing_bp
    app.register_blueprint(pricing_bp)
except Exception as e:
    print(f"Error registering pricing_bp: {e}", file=sys.stderr)

try:
    from routes.api_v1_routes import register_v1_routes
    register_v1_routes(app)
except Exception as e:
    print(f"Error registering v1 API routes: {e}", file=sys.stderr)


def _page_copy():
    return {**COPY, **EXPERIMENT_COPY}


_EXAMPLES_DIR = Path(__file__).resolve().parent / 'examples' / 'canonical'


def _list_canonical_experiments():
    items = []
    if not _EXAMPLES_DIR.is_dir():
        return items
    for path in sorted(_EXAMPLES_DIR.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            'id': data.get('id') or path.stem,
            'title': data.get('title') or path.stem,
            'description': data.get('description') or '',
        })
    return items


def _load_experiment(experiment_id: str):
    path = _EXAMPLES_DIR / f'{experiment_id}.json'
    if not path.is_file():
        # Also allow id field mismatch: scan
        for candidate in _EXAMPLES_DIR.glob('*.json'):
            try:
                data = json.loads(candidate.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get('id') == experiment_id:
                return data
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


@app.before_request
def _hosted_live_gate():
    if not path_requires_live(request.path):
        return None
    ok, err = check_live_allowed(request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown'))
    if ok:
        return None
    return jsonify(err), 503


@app.route('/')
def landing():
    """Research landing (hosted) or toolkit entry (local default)."""
    if is_hosted_mode():
        return render_template(
            'landing.html',
            allow_live=allow_live_inference(),
        )
    return render_template('index.html', results_copy=_page_copy())


@app.route('/lab')
@app.route('/app')
def lab():
    """Full analysis lab UI."""
    return render_template('index.html', results_copy=_page_copy())


@app.route('/about')
def about():
    return render_template(
        'landing.html',
        allow_live=allow_live_inference(),
    )


@app.route('/experiments')
def list_experiments():
    return render_template(
        'experiment.html',
        experiments=_list_canonical_experiments(),
        experiment=None,
    )


@app.route('/experiments/<experiment_id>')
def show_experiment(experiment_id):
    experiment = _load_experiment(experiment_id)
    if not experiment:
        return render_template(
            'experiment.html',
            experiments=_list_canonical_experiments(),
            experiment=None,
        ), 404
    return render_template('experiment.html', experiment=experiment, experiments=None)


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors - return JSON for API routes, HTML for pages."""
    import sys
    from flask import request
    
    # Emergency registration for assessment_bp if not found
    if request.path.startswith('/api/detect-foci') or request.path.startswith('/api/generate-output'):
        try:
            print(f"🔧 404 for {request.path} - attempting emergency registration...", file=sys.stderr)
            assessment_routes = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
            if len(assessment_routes) == 0:
                print("🔄 assessment_bp not registered, attempting import...", file=sys.stderr)
                from routes.assessment_routes import assessment_bp
                app.register_blueprint(assessment_bp)
                print("✅ Emergency registration successful!", file=sys.stderr)
                # After successful registration, tell client to retry
                return jsonify({
                    'error': 'Route was not registered, but is now. Please retry your request.',
                    'retry_possible': True
                }), 503 # Service Unavailable, client should retry
        except Exception as e:
            print(f"❌ Emergency registration failed: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    # Emergency registration for agent_bp if not found
    if request.path.startswith('/api/assess-chat-foci') or request.path.startswith('/api/generate-agent-response') or request.path.startswith('/api/build-agent-prompt'):
        try:
            print(f"🔧 404 for {request.path} - attempting emergency registration...", file=sys.stderr)
            agent_routes = [r for r in app.url_map.iter_rules() if 'agent' in r.endpoint]
            if len(agent_routes) == 0:
                print("🔄 agent_bp not registered, attempting import...", file=sys.stderr)
                from routes.agent_routes import agent_bp
                app.register_blueprint(agent_bp)
                print("✅ Emergency registration successful!", file=sys.stderr)
                # After successful registration, tell client to retry
                return jsonify({
                    'error': 'Route was not registered, but is now. Please retry your request.',
                    'retry_possible': True
                }), 503 # Service Unavailable, client should retry
        except Exception as e:
            print(f"❌ Emergency registration failed: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    # If this is generate-output, try to force register the blueprint
    if '/api/generate-output' in request.path:
        print(f"🔧 404 for /api/generate-output - attempting emergency registration...", file=sys.stderr)
        try:
            # Check if already registered
            assessment_routes = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
            if len(assessment_routes) == 0:
                print("   🔄 assessment_bp not registered, attempting import...", file=sys.stderr)
                from routes.assessment_routes import assessment_bp
                print(f"   ✅ Imported assessment_bp: {assessment_bp.name}", file=sys.stderr)
                app.register_blueprint(assessment_bp)
                print("   ✅ Emergency registration successful!", file=sys.stderr)
                # Verify registration worked
                assessment_routes_after = [r for r in app.url_map.iter_rules() if 'assessment' in r.endpoint]
                print(f"   ✅ {len(assessment_routes_after)} assessment routes now registered", file=sys.stderr)
                # Check if generate-output is now available
                generate_output_routes = [r for r in assessment_routes_after if '/api/generate-output' in str(r)]
                if generate_output_routes:
                    print(f"   ✅ /api/generate-output route is now available!", file=sys.stderr)
                    # Return a message asking user to retry (can't re-route POST in error handler)
                    return jsonify({
                        'error': 'Route was just registered. Please retry your request.',
                        'retry': True,
                        'message': 'The assessment blueprint was successfully registered. Please send your request again.'
                    }), 503  # Service Unavailable - temporary, should retry
                else:
                    print(f"   ⚠️ Route still not found after registration", file=sys.stderr)
            else:
                print(f"   ⚠️ assessment_bp already has {len(assessment_routes)} routes but route not found", file=sys.stderr)
        except Exception as e:
            print(f"   ❌ Emergency registration failed: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    # Log for debugging
    print(f"❌ 404 for {request.method} {request.path}", file=sys.stderr)
    # Get all registered routes
    all_routes = list(app.url_map.iter_rules())
    api_routes = [r for r in all_routes if str(r).startswith('/api/')]
    print(f"Total registered routes: {len(all_routes)}", file=sys.stderr)
    print(f"API routes: {len(api_routes)}", file=sys.stderr)
    
    # Check if the route exists with different method
    matching_routes = [r for r in all_routes if request.path in str(r)]
    if matching_routes:
        print(f"⚠️ Routes matching path (different method?):", file=sys.stderr)
        for route in matching_routes:
            print(f"   {list(route.methods)} {route} (endpoint: {route.endpoint})", file=sys.stderr)
    
    # Specifically check for generate-output
    if '/api/generate-output' in request.path:
        generate_output_routes = [r for r in all_routes if '/api/generate-output' in str(r)]
        print(f"🔍 generate-output routes found: {len(generate_output_routes)}", file=sys.stderr)
        for route in generate_output_routes:
            print(f"   {list(route.methods)} {route} (endpoint: {route.endpoint})", file=sys.stderr)
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': f'Endpoint not found: {request.method} {request.path}',
            'method': request.method,
            'path': request.path,
            'available_api_routes_count': len(api_routes),
            'matching_paths': [str(r) for r in matching_routes] if matching_routes else [],
            'hint': 'Check Vercel logs for route registration errors. Visit /api/routes to see all registered routes.'
        }), 404
    return render_template('index.html', results_copy=_page_copy()), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors - return JSON for API routes, HTML for pages."""
    import sys
    from flask import request
    print(f"Internal server error: {error}", file=sys.stderr)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error. Please try again later.'}), 500
    return render_template('index.html', results_copy=_page_copy()), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        from utils.inference_config import resolve_inference
        ai_gateway_key = os.getenv('AI_GATEWAY_API_KEY')
        try:
            cfg = resolve_inference()
            backend = cfg.get('backend')
            inference_ready = bool(cfg.get('api_key'))
        except Exception:
            backend = None
            inference_ready = False
        return jsonify({
            'status': 'ok',
            'hosted_mode': is_hosted_mode(),
            'allow_live_inference': allow_live_inference(),
            'ai_gateway_configured': bool(ai_gateway_key),
            'inference_backend': backend,
            'inference_ready': inference_ready,
            'vercel': os.getenv('VERCEL') is not None,
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


@app.route('/api/routes', methods=['GET'])
def list_routes():
    """List all registered routes for debugging."""
    import sys
    routes_info = []
    for rule in app.url_map.iter_rules():
        routes_info.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule),
            'is_api': str(rule).startswith('/api/')
        })
    
    # Sort by path
    routes_info.sort(key=lambda x: x['path'])
    
    # Log to stderr for Vercel logs
    print(f"Total routes registered: {len(routes_info)}", file=sys.stderr)
    api_routes = [r for r in routes_info if r['is_api']]
    print(f"API routes: {len(api_routes)}", file=sys.stderr)
    for route in api_routes[:20]:  # First 20
        print(f"  {route['methods']} {route['path']}", file=sys.stderr)
    
    return jsonify({
        'total_routes': len(routes_info),
        'api_routes': len(api_routes),
        'routes': routes_info
    })


if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '127.0.0.1')
    # Use waitress with 10-minute timeout for long-running ablation analysis
    serve(app, host=host, port=port, threads=4, channel_timeout=600)


