"""Scenario ablation HTTP contracts: input binding, refinement, judge role."""

from unittest.mock import Mock

import numpy as np
import pytest
from flask import Flask

from routes.ablation_routes import ablation_bp
from services.ablation_service import AblationService


SCENARIO = {
    'version': 1,
    'messages': [
        {
            'id': 'rules',
            'role': 'system',
            'content': 'Alpha rule. Beta rule.',
            'analysis_mode': 'analyse',
        },
        {
            'id': 'question',
            'role': 'user',
            'content': 'default question',
            'analysis_mode': 'retain',
            'input_name': 'customer_message',
        },
    ],
}

FOCI = [
    {
        'focus': 'Alpha',
        'spans': [{
            'message_id': 'rules', 'char_start': 0, 'char_end': 11,
            'text_snapshot': 'Alpha rule.',
        }],
    },
    {
        'focus': 'Beta',
        'spans': [{
            'message_id': 'rules', 'char_start': 12, 'char_end': 22,
            'text_snapshot': 'Beta rule.',
        }],
    },
]


class FakeEmbeddings:
    def batch_embeddings_with_usage(self, texts):
        return (
            [np.array([1.0, float(index + 1)]) for index, _ in enumerate(texts)],
            len(texts),
        )


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(ablation_bp)
    app.config['TESTING'] = True

    calls = []

    def respond(**kwargs):
        calls.append(kwargs['messages'])
        return {
            'content': f'reply {len(calls)}',
            'usage': {'prompt_tokens': 3, 'completion_tokens': 2},
        }

    provider = Mock()
    provider.chat_completion.side_effect = respond
    assessor = Mock()
    assessor.provider = provider
    assessor.provider_name = 'openai'

    monkeypatch.setattr('routes.ablation_routes.get_assessor', lambda data=None: assessor)
    monkeypatch.setattr('routes.ablation_routes.EmbeddingService', FakeEmbeddings)
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_args: None)
    saved = []
    monkeypatch.setattr(
        'services.checkpoint_service.CheckpointService.save_checkpoint',
        lambda self, session_id, data, kind: saved.append(data) or session_id,
    )
    return app.test_client(), calls, saved


def test_scenario_ablation_accepts_omitted_inputs_and_uses_message_defaults(client):
    http, calls, _saved = client

    response = http.post('/api/ablation-analysis', json={
        'scenario': SCENARIO,
        'foci': FOCI,
        'n_baseline': 2,
        'n_ablated': 2,
        'n_permutations': 32,
    })

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['scenario_metadata']['input_binding']['used_defaults'] == [
        'customer_message'
    ]
    assert payload['scenario_metadata']['input_binding']['missing'] == []
    assert all(call[-1]['content'] == 'default question' for call in calls)


def test_ablation_score_records_bound_scenario_for_follow_up_refinement(client):
    http, _calls, saved = client

    response = http.post('/api/ablation-score', json={
        'scenario': SCENARIO,
        'foci': FOCI,
        'inputs': {'customer_message': 'My dog is coughing'},
        'baseline_outputs': ['one', 'two', 'three'],
        'ablated_outputs': {'0': ['a', 'b'], '1': ['c', 'd']},
        'n_permutations': 32,
    })

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['scenario']['messages'][1]['content'] == 'My dog is coughing'
    assert payload['scenario_metadata']['input_binding']['unused'] == []
    assert saved[0]['scenario']['messages'][1]['content'] == 'My dog is coughing'


def test_scenario_refinement_of_one_focus_returns_refreshed_top_level_metrics(client):
    http, calls, _saved = client

    response = http.post('/api/ablation-refine-stability', json={
        'scenario': SCENARIO,
        'foci': FOCI,
        'focus_index': 1,
        'inputs': {'customer_message': 'My dog is coughing'},
        'baseline_outputs': ['one', 'two', 'three'],
        'ablated_outputs': ['c', 'd'],
        'n_additional': 2,
        'n_permutations': 32,
    })

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['focus_index'] == 1
    assert payload['focus'] == 'Beta'
    assert payload['n_ablated_samples'] == 4
    assert payload['ablation_stability'] is not None
    assert payload['permutation']['p_value'] is not None
    assert payload['cost_breakdown'] is not None
    assert 'score' not in payload
    assert len(calls) == 2
    assert all(call[0]['content'] == 'Alpha rule. ' for call in calls)


def test_behavioral_outcome_dispersion_judges_with_the_analysis_model(client, monkeypatch):
    http, _calls, _saved = client
    used = {}

    def capture(self, **kwargs):
        used['model'] = self.model
        return {0: {'delta': 0.0}}

    monkeypatch.setattr(
        AblationService, 'attach_behavioral_outcome_dispersion', capture
    )

    response = http.post('/api/ablation-behavioral-outcome-dispersion', json={
        'analysis_model': 'gpt-4o',
        'mut_model': 'gpt-4o-mini',
        'baseline_outputs': ['one', 'two'],
        'ablated_outputs': {'0': ['a', 'b']},
        'behavioral_criterion': 'mentions the refund policy',
    })

    assert response.status_code == 200, response.get_json()
    assert used['model'] == 'gpt-4o'
