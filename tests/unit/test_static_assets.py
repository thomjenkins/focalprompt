"""Fresh asset URLs must not depend on serverless bundle timestamps or size."""
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from flask import Flask, url_for

from utils.static_assets import register_asset_versions


def test_same_size_same_mtime_edit_gets_a_new_content_version(tmp_path):
    path = tmp_path / 'app.js'
    path.write_text('const version = 1;')
    fixed_time = 1540000000
    os.utime(path, (fixed_time, fixed_time))
    app = Flask(__name__, static_folder=str(tmp_path), static_url_path='/static')
    register_asset_versions(app)
    with app.test_request_context():
        before = url_for('static', filename='app.js')
        assert url_for('static', filename='app.js') == before
        path.write_text('const version = 2;')  # Same length; deployment mtime unchanged.
        os.utime(path, (fixed_time, fixed_time))
        after = url_for('static', filename='app.js')
        assert before != after
        assert parse_qs(urlsplit(after).query)['v'] == [hashlib.sha256(path.read_bytes()).hexdigest()[:16]]
        assert url_for('static', filename='missing.js') == '/static/missing.js'
        assert url_for('static', filename='app.js', v='explicit') == '/static/app.js?v=explicit'
        assert url_for('static', filename='../private.js') == '/static/../private.js'


def test_lab_and_replay_link_to_the_current_code_and_styles(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    client = app.test_client()
    for route in ('/lab', '/app', '/', '/demo/lisbon'):
        html = client.get(route).get_data(as_text=True)
        assets = re.findall(r'(?:src|href)="(/static/[^" ]+\.(?:js|css)[^" ]*)"', html)
        assert len(assets) > 10
        for asset in assets:
            url = urlsplit(asset)
            path = Path(app.static_folder) / url.path.removeprefix('/static/')
            assert parse_qs(url.query)['v'] == [hashlib.sha256(path.read_bytes()).hexdigest()[:16]]
        assert any('/static/js/order_workflow.js?v=' in asset for asset in assets)
    # Fingerprinting is a cache key, not a separate serving path.
    response = client.get(next(asset for asset in assets if '/order_workflow.js?' in asset))
    assert response.status_code == 200
    assert response.data == (Path(app.static_folder) / 'js/order_workflow.js').read_bytes()
