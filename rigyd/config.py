"""Persisted CLI/SDK configuration (API key, base URL).

Stored as JSON at ``$XDG_CONFIG_HOME/rigyd/config.json`` (default
``~/.config/rigyd/config.json``) with 0600 permissions. Resolution order for
the key is: explicit argument > ``RIGYD_API_KEY`` env > config file.
"""

from __future__ import annotations

import json
import os

DEFAULT_BASE_URL = "https://api.rigyd.com/api"


def config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, "rigyd", "config.json")


def load() -> dict:
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(api_key: str | None = None, base_url: str | None = None) -> str:
    """Merge the given values into the config file; return its path."""
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = load()
    if api_key is not None:
        data["api_key"] = api_key.strip()
    if base_url is not None:
        data["base_url"] = base_url.strip()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.chmod(path, 0o600)
    return path


def resolve_api_key(explicit: str | None = None) -> str:
    return explicit or os.environ.get("RIGYD_API_KEY") or load().get("api_key", "")


def resolve_base_url(explicit: str | None = None) -> str:
    return (
        explicit
        or os.environ.get("RIGYD_BASE_URL")
        or load().get("base_url")
        or DEFAULT_BASE_URL
    )
