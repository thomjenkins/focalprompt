"""BYO inference config resolution."""

import os
from unittest.mock import patch

import pytest

from utils.inference_config import resolve_inference, resolve_embedding_config


def test_gateway_is_default_when_key_present(monkeypatch):
    monkeypatch.setenv('AI_GATEWAY_API_KEY', 'gw-test')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('FOCALPROMPT_BACKEND', raising=False)
    cfg = resolve_inference({'provider': 'openai', 'model': 'gpt-4o-mini'})
    assert cfg['backend'] == 'vercel_gateway'
    assert cfg['api_key'] == 'gw-test'


def test_direct_openai_when_forced(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    monkeypatch.setenv('AI_GATEWAY_API_KEY', 'gw-test')
    cfg = resolve_inference({'backend': 'direct', 'provider': 'openai'})
    assert cfg['backend'] == 'direct'
    assert cfg['api_key'] == 'sk-test'


def test_openai_compatible_ollama(monkeypatch):
    monkeypatch.delenv('AI_GATEWAY_API_KEY', raising=False)
    cfg = resolve_inference({
        'backend': 'ollama',
        'model': 'llama3.2',
        'provider': 'openai',
    })
    assert cfg['backend'] == 'openai_compatible'
    assert '11434' in cfg['base_url']


def test_missing_credentials_raises(monkeypatch):
    for key in (
        'AI_GATEWAY_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
        'GOOGLE_API_KEY', 'XAI_API_KEY', 'FOCALPROMPT_BASE_URL', 'OPENAI_BASE_URL',
        'FOCALPROMPT_BACKEND',
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match='No inference credentials'):
        resolve_inference({'provider': 'openai'})
