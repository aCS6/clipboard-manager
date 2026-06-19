# Clipboard Manager

[![CI](https://github.com/aCS6/clipboard-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/aCS6/clipboard-manager/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Platform: Ubuntu 24.04](https://img.shields.io/badge/platform-Ubuntu%2024.04-orange.svg)](https://ubuntu.com/)
[![Latest Release](https://img.shields.io/github/v/release/aCS6/clipboard-manager)](https://github.com/aCS6/clipboard-manager/releases/latest)

A lightweight clipboard history manager for Ubuntu 24.04 / GNOME 46.

**Features:** automatic text & image capture, history popup, delete, private mode, tray icon, corner-anchored popup.

---

## ⬇️ Install (easiest)

**Download the `.deb` from the [latest release](https://github.com/aCS6/clipboard-manager/releases/latest) and install:**

```bash
wget https://github.com/aCS6/clipboard-manager/releases/latest/download/clipboard-manager_1.0.0-1_all.deb
sudo apt install ./clipboard-manager_1.0.0-1_all.deb
clipboard-manager
```

`apt install ./` automatically pulls in all required dependencies. The app appears in your GNOME app grid after install.

---

## Usage

- **Left-click** tray icon → opens clipboard history popup
- **Click any item** → copies it back to the clipboard, popup closes
- **🗑 icon** on each row → deletes that entry
- **Private mode** (footer toggle) → pauses capture without quitting
- **Settings** (right-click tray → Settings) → history limit, poll interval, popup position, autostart
- **Clear all** (popup footer) → clears history with confirmation

---

## Run from source

```bash
# Install system dependencies
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0

git clone https://github.com/aCS6/clipboard-manager
cd clipboard-manager
make run
```

---

## Autostart

Enable from the Settings dialog in the app, or manually:

```bash
make autostart-enable
```

Or as a systemd user service:

```bash
make service-install
```

---

## Uninstall

```bash
# If installed via .deb
sudo dpkg -r clipboard-manager

# Remove user data
rm -rf ~/.local/share/clipboard-manager ~/.config/clipboard-manager
rm -f ~/.config/autostart/clipboard-manager.desktop
```

---

## Development

```bash
make test    # run pytest (no display needed)
make run     # run the app
make watch   # headless watcher
make deb     # build .deb → packages/
make clean   # clean artifacts
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Architecture note (Wayland)

GNOME's Mutter does **not** implement `wlr-data-control`, so background clipboard access requires running as an **XWayland client** (`GDK_BACKEND=x11`). Set automatically by the launcher and `.desktop` file. Same approach used by CopyQ.

---

## Data locations

| Path | Contents |
|------|----------|
| `~/.local/share/clipboard-manager/history.db` | SQLite database |
| `~/.local/share/clipboard-manager/images/` | Captured images |
| `~/.config/clipboard-manager/config.json` | Settings |
| `~/.config/autostart/clipboard-manager.desktop` | Autostart (if enabled) |

---

## Roadmap

- [ ] Publish to Ubuntu PPA (`apt install` without downloading `.deb`)
- [ ] Publish to PyPI (`pip install clipboard-manager`)
- [ ] Multi-monitor support
- [ ] Global keyboard shortcut

---

## License

MIT © 2026 [aCS6](https://github.com/aCS6)
