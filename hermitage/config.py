"""Configuration management — YAML file at ~/.config/hermitage/config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml


_CONFIG_DIR = Path.home() / ".config" / "hermitage"
_CONFIG_PATH = _CONFIG_DIR / "config.yaml"

_DEFAULTS = {
    "library_path": "",
    "sort_field": "title",
    "sort_ascending": True,
}

_config: dict | None = None


def config_path() -> Path:
    """Return the path to the config file."""
    return _CONFIG_PATH


def config_exists() -> bool:
    """Check whether a config file exists on disk."""
    return _CONFIG_PATH.is_file()


def load_config() -> dict:
    """Load config from disk, merging with defaults. Cached after first call."""
    global _config
    if _config is not None:
        return _config

    cfg = dict(_DEFAULTS)
    if _CONFIG_PATH.is_file():
        try:
            with open(_CONFIG_PATH) as f:
                on_disk = yaml.safe_load(f)
            if isinstance(on_disk, dict):
                cfg.update(on_disk)
        except Exception:
            pass

    _config = cfg
    return _config


def save_config(cfg: dict | None = None):
    """Write config to disk. If cfg is None, saves the current in-memory config."""
    global _config
    if cfg is not None:
        _config = cfg

    if _config is None:
        return

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        yaml.safe_dump(_config, f, default_flow_style=False, sort_keys=True)


def get(key: str, default=None):
    """Get a config value."""
    return load_config().get(key, default)


def set_value(key: str, value):
    """Set a config value and persist to disk."""
    cfg = load_config()
    cfg[key] = value
    save_config()


def reload_config():
    """Force a re-read from disk."""
    global _config
    _config = None
    load_config()
