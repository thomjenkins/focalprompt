"""Planning and scoring endpoints; generation uses /api/ablation-sample."""
from datetime import datetime, timezone
import uuid

from flask import Blueprint, jsonify, request

from routes.ablation_routes import _ablation_service
from routes.http_errors import internal_error
from services.checkpoint_service import CheckpointService
from services.singleton_service import build_plan, score_samples
from utils.inference_scenario import scenario_from_request
from utils.json_safe import sanitize_non_finite

singleton_bp = Blueprint('singleton', __name__)


@singleton_bp.route('/api/singleton-<action>', methods=['POST'])
def singleton(action):
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            raise ValueError('Request must be a JSON object.')
        scenario, _ = scenario_from_request(data)
        kwargs = {key: data.get(key, default) for key, default in
                  [('n_baseline', 10), ('n_ablated', 5), ('temperature', 0.7)]}
        if action == 'plan':
            result = build_plan(scenario, data.get('foci'), inputs=data.get('inputs'), **kwargs)
        elif action == 'score':
            if data.get('inputs') is not None:
                raise ValueError('Score the bound scenario returned by the plan; do not rebind inputs.')
            result = score_samples(_ablation_service(data), scenario, data.get('foci'), data.get('samples'),
                                   **kwargs, **{key: data[key] for key in ['n_permutations', 'alpha', 'permutation_seed'] if key in data})
            result = sanitize_non_finite(result)
            session_id = str(uuid.uuid4())
            saved = CheckpointService().save_checkpoint(session_id, {
                'session_id': session_id, 'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'singleton_analysis', 'workspace_version': 2, 'result_data': result, 'complete': True,
            }, 'singleton_analysis')
            result['checkpoint'] = {'session_id': session_id, 'saved': saved, 'type': 'singleton_analysis'}
        else:
            return jsonify({'error': 'Unknown singleton action.'}), 404
        return jsonify(sanitize_non_finite(result))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        return internal_error('singleton_analysis', error)
