#!/usr/bin/env python3
"""
Batch analysis route handlers.

CSV upload parsing, SSE batch ablation, and checkpoint list/load.
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
import json

from services.checkpoint_service import CheckpointService
from utils.batch_csv import parse_batch_csv_bytes, parse_result_to_response
from utils.data_processing import (
    calculate_statistics_from_results,
    calculate_focus_distribution_statistics,
)
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields


batch_bp = Blueprint('batch', __name__)


@batch_bp.route('/api/parse-batch-csv', methods=['POST'])
def parse_batch_csv():
    """
    Parse a CSV upload into batch analysis pairs.

    Deterministic application logic (not an LLM call). Expects multipart
    form field ``file``. See ``utils.batch_csv`` for column aliases and limits.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided', 'errors': ['No file provided'], 'pairs': []}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected', 'errors': ['No file selected'], 'pairs': []}), 400

        raw = file.read()
        result = parse_batch_csv_bytes(raw)
        body, status = parse_result_to_response(result)
        return jsonify(body), status
    except Exception as e:
        return internal_error(
            'batch_parse_csv',
            e,
            extra={'errors': [], 'pairs': []},
        )


@batch_bp.route('/api/list-checkpoints', methods=['GET'])
def list_checkpoints():
    """List all available checkpoints."""
    try:
        checkpoint_type = request.args.get('type', 'batch_analysis')
        checkpoint_service = CheckpointService()
        checkpoints = checkpoint_service.list_checkpoints(checkpoint_type)
        return jsonify({'checkpoints': checkpoints})
    except ValueError:
        return jsonify({'error': 'invalid session_id or type'}), 400
    except Exception as e:
        return internal_error('batch_list_checkpoints', e)


@batch_bp.route('/api/get-checkpoint', methods=['GET'])
def get_checkpoint():
    """Retrieve checkpoint data for a session."""
    try:
        session_id = request.args.get('session_id')
        checkpoint_type = request.args.get('type', 'batch_analysis')
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400

        checkpoint_service = CheckpointService()
        checkpoint = checkpoint_service.load_checkpoint(session_id, checkpoint_type)

        if checkpoint:
            # Always derive batch statistics from pair results so logic stays in sync
            if checkpoint_type == 'batch_analysis':
                pair_results = checkpoint.get('pair_results', [])
                if pair_results:
                    checkpoint['statistics'] = calculate_statistics_from_results(pair_results)
                    checkpoint['focus_distribution_statistics'] = (
                        calculate_focus_distribution_statistics(pair_results)
                    )

            return jsonify(checkpoint)
        else:
            return jsonify({'error': 'Checkpoint not found'}), 404
    except ValueError:
        return jsonify({'error': 'invalid session_id or type'}), 400
    except Exception as e:
        return internal_error('batch_get_checkpoint', e)


@batch_bp.route('/api/batch-aggregate', methods=['POST'])
def batch_aggregate():
    """
    Aggregate already-scored pair results into batch statistics.

    Deterministic (no LLM). Used by the client-paced batch runner after each
    pair is sampled/scored via /api/ablation-sample and /api/ablation-score.
    """
    try:
        data = request.json or {}
        pair_results = data.get('pair_results') or data.get('results') or []
        if not isinstance(pair_results, list):
            return jsonify({'error': 'pair_results must be a list'}), 400
        statistics = calculate_statistics_from_results(pair_results)
        focus_distribution_statistics = calculate_focus_distribution_statistics(
            pair_results
        )
        return jsonify({
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'pair_results': pair_results,
            'results': pair_results,
        })
    except Exception as e:
        return internal_error('batch_aggregate', e)


@batch_bp.route('/api/batch-analysis-stream', methods=['POST'])
@batch_bp.route('/api/batch-ablation-analysis-stream', methods=['POST'])  # legacy URL
@stream_with_context
def batch_analysis_stream():
    """Run batch ablation analysis with streaming progress updates via SSE."""
    from services.assessor_factory import get_assessor
    from services.batch_analysis_service import BatchAnalysisService
    from services.embedding_service import EmbeddingService
    from services.cost_calculator import CostCalculator
    from services.checkpoint_service import CheckpointService
    from services.assessment_service import AssessmentService

    def generate():
        try:
            data = request.json or {}
            pairs = data.get('pairs', [])
            foci_list = data.get('foci', [])
            num_samples = data.get('num_samples')
            n_baseline = data.get('n_baseline', 10)
            n_ablated = data.get('n_ablated', 5)
            n_permutations = data.get('n_permutations', 10000)
            alpha = data.get('alpha', 0.05)
            permutation_seed = data.get('permutation_seed')
            temperature = data.get('temperature', 0.7)
            session_id = data.get('session_id')
            resume = data.get('resume', False)

            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'At least one pair is required'})}\n\n"
                return

            if not foci_list or len(foci_list) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Foci are required'})}\n\n"
                return

            fields = request_inference_fields(data, model_role='mut')
            model = fields['model']
            provider = fields['provider']

            assessor = get_assessor(data=fields)
            provider_instance = assessor.provider
            assessment_service = AssessmentService(assessor)

            embedding_service = EmbeddingService()
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()

            batch_service = BatchAnalysisService(
                provider_instance,
                model,
                fields.get('api_key'),
                embedding_service,
                cost_calculator,
                checkpoint_service,
                assessment_service=assessment_service,
                provider_name=getattr(assessor, 'provider_name', provider),
            )

            for chunk in batch_service.stream_batch_analysis(
                pairs,
                foci_list,
                num_samples=num_samples,
                session_id=session_id,
                resume=resume,
                n_baseline=n_baseline,
                n_ablated=n_ablated,
                n_permutations=n_permutations,
                alpha=alpha,
                permutation_seed=permutation_seed,
                temperature=temperature,
            ):
                yield chunk

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@batch_bp.route('/api/test-api-key', methods=['POST'])
def test_api_key():
    """Test if an API key is valid for the specified provider."""
    try:
        data = request.json or {}
        api_key = data.get('api_key', '')
        provider = data.get('provider', 'openai')

        if not api_key:
            return jsonify({'valid': False, 'error': 'No API key provided'}), 400

        try:
            from core.llm_providers import get_provider
            test_provider = get_provider(provider, api_key)
            test_provider.list_models()
            return jsonify({'valid': True})
        except Exception as e:
            return jsonify({'valid': False, 'error': str(e)}), 400

    except Exception as e:
        return internal_error('batch_test_api_key', e, extra={'valid': False})
