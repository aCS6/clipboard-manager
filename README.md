# Clipboard Manager

[![CI](https://github.com/aCS6/clipboard-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/aCS6/clipboard-manager/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Platform: Ubuntu 24.04](https://img.shields.io/badge/platform-Ubuntu%2024.04-orange.svg)](https://ubuntu.com/)

A lightweight clipboard history manager for Ubuntu 24.04 / GNOME 46.

**Features:** automatic text & image capture, searchable history, delete, private mode, tray icon, corner-anchored popup.

---

## Running the app

**1. Install system dependencies (one-time):**
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0
```

**2. Run:**
```bash
git clone https://github.com/aCS6/clipboard-manager
cd clipboard-manager
make run
```

A clipboard icon appears in the GNOME top bar. Left-click opens history, right-click for menu.

**If the tray icon doesn't show**, verify the AppIndicator extension is enabled:
```bash
gnome-extensions list --enabled | grep appindicator
# If missing:
gnome-extensions enable appindicator@rgcjonas.gmail.com
```

**To test the watcher headlessly** (no UI):
```bash
make watch
```

---

## Usage

- **Left-click** tray icon → opens clipboard history popup
- **Click any item** → copies it back to the clipboard, popup closes
- **🗑 icon** on each row → deletes that entry
- **Private mode** (footer toggle) → pauses capture without quitting
- **Settings** (right-click tray → Settings) → history limit, poll interval, popup position, autostart
- **Clear all** (popup footer) → clears unpinned history with confirmation

---

## Quick install options

### Run from source (recommended for now)
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0
git clone https://github.com/aCS6/clipboard-manager
cd clipboard-manager
make run
```

### pip _(coming soon — see [#roadmap](#roadmap))_
```bash
pip install clipboard-manager
clipboard-manager
```

### apt / PPA _(coming soon — see [#roadmap](#roadmap))_
```bash
sudo add-apt-repository ppa:aCS6/clipboard-manager
sudo apt install clipboard-manager
```

---

## Autostart

Enable from Settings dialog, or manually:
```bash
make autostart-enable
```

Or as a systemd user service:
```bash
make service-install
```

---

## Development

```bash
make test       # run pytest (no display needed)
make run        # run the app
make watch      # run headless watcher
make clean      # clean build artifacts
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full contribution guide.

---

## Architecture note (Wayland)

GNOME's Mutter does **not** implement `wlr-data-control`, so background clipboard access requires running as an **XWayland client** (`GDK_BACKEND=x11`). Set automatically by the launcher. Same approach used by CopyQ.

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

- [ ] **Publish to PyPI** — `make pip-build` then `twine upload`
- [ ] **Publish to Ubuntu PPA** — `make deb` + Launchpad PPA upload
- [ ] Multi-monitor support
- [ ] Global keyboard shortcut

---

## Uninstall

```bash
make service-uninstall
make autostart-disable
make purge
pip uninstall clipboard-manager   # if installed via pip
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

---

## License

MIT © 2026 aCS6
