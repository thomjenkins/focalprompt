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
