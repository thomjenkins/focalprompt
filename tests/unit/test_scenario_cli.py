"""CLI scenario source selection."""

import json

import pytest

from focalprompt.cli import main


def test_cli_scenario_file_is_mutually_exclusive_and_forwarded(tmp_path, monkeypatch):
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps({
        'version': 1,
        'messages': [
            {'id': 'user', 'role': 'user', 'content': 'hello', 'analysis_mode': 'analyse'}
        ],
    }))
    seen = {}

    def fake_detect(prompt, **kwargs):
        seen['prompt'] = prompt
        seen.update(kwargs)
        return {'foci': []}

    monkeypatch.setattr('focalprompt.api.detect_foci', fake_detect)
    assert main(['foci', '--scenario', str(path)]) == 0
    assert seen['prompt'] is None
    assert seen['scenario'] == str(path)

    with pytest.raises(SystemExit):
        main(['foci', 'legacy', '--scenario', str(path)])


def test_assess_accepts_options_between_prompt_and_completion(monkeypatch, capsys):
    from unittest.mock import Mock

    from core.focal_assessor import FocalAssessor

    provider = Mock()
    provider.chat_completion.return_value = {
        'content': json.dumps({
            'foci': [{
                'focus': 'Brevity',
                'prompt_section': 'Be brief.',
                'score': 100,
                'explanation': 'The answer is concise.',
            }],
            'overall_summary': 'Concise.',
        }),
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0},
    }
    assessor = FocalAssessor(provider_instance=provider)
    monkeypatch.setattr('focalprompt.api.get_assessor', lambda **_kwargs: assessor)

    assert main(['assess', 'Be brief.', '--model', 'gpt-4o-mini', 'A short answer.']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['foci'][0]['focus'] == 'Brevity'
    assert result['foci'][0]['score'] == 100


@pytest.mark.parametrize('arguments', [
    ['assess', 'prompt', '--scenario', 'scenario.json', 'completion'],
    ['assess', 'completion'],
])
def test_assess_rejects_ambiguous_or_missing_source(arguments):
    with pytest.raises(SystemExit) as exc:
        main(arguments)
    assert exc.value.code == 2
