"""Dedicated Jev evaluation endpoints; chat generation uses the existing compiler."""

from flask import Blueprint, jsonify, request

from core.gateway_evaluation import EvaluationError, GatewayEvaluation
from routes.http_errors import internal_error
from services import jev_focus_service as service


jev_focus_bp = Blueprint('jev_focus', __name__)


@jev_focus_bp.route('/api/jev-focus/<action>', methods=['POST'])
def jev_focus(action):
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            raise ValueError('Request must be a JSON object.')
        scenario, foci = data.get('scenario'), data.get('foci')
        if action == 'select':
            result = service.select(GatewayEvaluation(), scenario, foci, data.get('threshold', 0.5))
        elif action == 'order-next':
            result = service.order_next(GatewayEvaluation(), scenario, foci, data.get('selected_indices'),
                                        data.get('message_id'), data.get('prefix'))
        elif action == 'compose':
            result = service.compose(scenario, foci, data.get('selected_indices'), data.get('orders'))
        else:
            return jsonify({'error': 'Unknown Jev experiment action.'}), 404
        return jsonify(result)
    except EvaluationError as exc:
        return jsonify({'error': str(exc), 'code': 'jev_evaluation_error'}), exc.status
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return internal_error('jev_focus', exc)
