"""Content-based URLs for browser code, independent of deployment file timestamps."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from werkzeug.utils import safe_join


@lru_cache(maxsize=256)
def _fingerprint(path, mtime_ns, ctime_ns, size):
    # Stat values invalidate the local-development cache; the public version is
    # always based on bytes. Serverless bundles may normalize every file's mtime.
    return sha256(Path(path).read_bytes()).hexdigest()[:16]


def register_asset_versions(app):
    @app.url_defaults
    def version_browser_assets(endpoint, values):
        filename = values.get('filename', '')
        if endpoint != 'static' or 'v' in values or Path(filename).suffix not in ('.js', '.css'):
            return
        path = safe_join(app.static_folder, filename)
        if path is None:
            return
        try:
            stat = Path(path).stat()
            values['v'] = _fingerprint(path, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
        except OSError:
            # Preserve Flask's normal missing-file response rather than breaking
            # an entire page if an optional asset is absent.
            return
