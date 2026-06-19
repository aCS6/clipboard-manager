"""Write or remove the ~/.config/autostart/clipboard-manager.desktop file."""
import os
from pathlib import Path

_AUTOSTART_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
_DESKTOP_DEST = _AUTOSTART_DIR / "clipboard-manager.desktop"

_DESKTOP_CONTENT = """\
[Desktop Entry]
Type=Application
Name=Clipboard Manager
Comment=Lightweight clipboard history for GNOME
Exec=env GDK_BACKEND=x11 clipboard-manager
Icon=clipboard-manager
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


def set_autostart(enabled: bool) -> None:
    if enabled:
        _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        _DESKTOP_DEST.write_text(_DESKTOP_CONTENT)
    else:
        _DESKTOP_DEST.unlink(missing_ok=True)
