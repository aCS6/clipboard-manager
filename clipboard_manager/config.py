import json
import os
import tempfile
from pathlib import Path

_CFG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "clipboard-manager"
_CFG_FILE = _CFG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
    "history_limit": 50,
    "poll_interval_ms": 750,
    "popup_corner": "top-right",
    "autostart_enabled": True,
    "private_mode": False,
    "max_image_size_mb": 8,
}


def load_config() -> dict:
    if not _CFG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    with _CFG_FILE.open() as f:
        data = json.load(f)
    return {**DEFAULT_CONFIG, **data}


def save_config(cfg: dict) -> None:
    _CFG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _CFG_DIR / ".config.tmp"
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(_CFG_FILE)
