"""Versioned static asset URLs for long-lived browser caching.

Repository assets (CSS, JS, icons) are referenced through ``static_url``
which appends a content hash as a ``v`` query parameter. The static file
handler treats any request carrying ``v`` as immutable, so browsers keep
those files for a year and re-download only when the content (and hence
the hash) changes. Uploaded images keep plain URLs and a short cache.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
STATIC_URL_PREFIX = "/static"
_VERSION_HASH_LENGTH = 12


@lru_cache(maxsize=256)
def asset_version(relative_path: str) -> str | None:
    """Return a short content hash for a repository static file, if it exists."""

    file_path = STATIC_DIR / relative_path
    try:
        content = file_path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(content).hexdigest()[:_VERSION_HASH_LENGTH]


def static_url(relative_path: str) -> str:
    """Build a cache-busting URL for a file under ``app/static``."""

    normalized_path = relative_path.lstrip("/")
    url = f"{STATIC_URL_PREFIX}/{normalized_path}"
    version = asset_version(normalized_path)
    if version is None:
        return url
    return f"{url}?v={version}"
