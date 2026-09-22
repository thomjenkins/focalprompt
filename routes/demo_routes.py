"""Guided, isolated replay in the real analysis lab."""
from functools import lru_cache
import gzip
from pathlib import Path

from flask import Blueprint, Response, abort, render_template
from utils.experiment_config import EXPERIMENT_COPY
from utils.results_copy import COPY

demo_bp = Blueprint('demo', __name__)
FIXTURES = {'lisbon': {'gpt4omini': 'lisbon/pup4ominiFull.json'}}
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'examples' / 'demos'


@demo_bp.get('/demo/<demo_id>')
def presentation(demo_id):
    if demo_id not in FIXTURES:
        abort(404)
    return render_template('index.html', results_copy={**COPY, **EXPERIMENT_COPY}, replay=demo_id)


@lru_cache(maxsize=8)
def _compressed_fixture(relative_path):
    # The original export stays byte-for-byte intact. Compression keeps this 7MB
    # workspace under serverless response limits (and makes initial loading quick).
    return gzip.compress((FIXTURE_ROOT / relative_path).read_bytes(), mtime=0)


@demo_bp.get('/demo/<demo_id>/workspaces/<fixture_id>.json')
def workspace(demo_id, fixture_id):
    path = FIXTURES.get(demo_id, {}).get(fixture_id)
    if not path:
        abort(404)
    return Response(_compressed_fixture(path), mimetype='application/json', headers={
        'Content-Encoding': 'gzip', 'Cache-Control': 'public, max-age=0, must-revalidate',
        'Vary': 'Accept-Encoding', 'X-Content-Type-Options': 'nosniff',
    })
