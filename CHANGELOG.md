# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## [1.0.0] - 2026-06-19

### Added
- Automatic clipboard capture for text and images (XWayland polling via GTK)
- Searchable history popup anchored to a screen corner
- Per-item delete action
- Private mode toggle (pauses capture without quitting)
- Settings dialog: history limit, poll interval, popup corner, autostart
- SQLite-backed persistent storage with image file cache
- SHA-256 de-duplication (no duplicate rows for repeated copies)
- History trimming respects a configurable cap (default 50 unpinned items)
- Tray icon via `Gtk.StatusIcon` with left-click to open history
- Single-instance enforcement via `Gtk.Application` unique app ID
- Autostart via `~/.config/autostart/` desktop entry
- Optional systemd `--user` service unit
- `make` targets for run, test, pip-build, deb, autostart, service
