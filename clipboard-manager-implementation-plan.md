# Clipboard Manager for Ubuntu 24.04 — Implementation Plan

**Status:** Draft v1
**Owner:** Nahid (Vivasoft)
**Target platform:** Ubuntu 24.04 LTS, GNOME 46, Wayland session (confirmed via `echo $XDG_SESSION_TYPE`)
**Language:** Python 3.12 + PyGObject (GTK3)
**Last updated:** 2026-06-17

> How to use this doc: every task in §8 is self-contained. If you're picking up TASK-403 cold, you don't need to read TASK-001 through 402 — just read §6 (interfaces) and §5 (data model) for context, then do the task. Cross-references use section numbers, e.g. "per §6.1".

---

## 1. Business context

### 1.1 Problem
Vivasoft engineers regularly copy snippets of text (tokens, IDs, code, log lines) and screenshots/images while working across terminals, browsers, and tools. Ubuntu's GNOME desktop has no built-in clipboard history — once you copy something new, the old one is gone. Existing third-party tools (CopyQ, Diodon, GNOME Shell extensions) are either heavier than necessary, tied to a Shell extension that's awkward to maintain in-house, or don't match the desired UX. This project builds a small, purpose-fit, in-house clipboard manager.

### 1.2 Goals (v1)
- Automatically capture copied text and images into a searchable history.
- Tray-icon-triggered popup to browse, search, pin, copy back, and delete history items.
- Low resource footprint — this runs in the background all day, every day, on every dev machine.
- Simple enough that any team member can read this doc and extend it.

### 1.3 Non-goals (v1)
- No cross-device sync or cloud storage.
- No rich-text/HTML formatting preservation (plain text + images only).
- No global keyboard shortcut (Wayland makes this disproportionately fiddly — see §12).
- No Windows/macOS support.

### 1.4 Success criteria
- Idle RAM usage stays in the tens-of-MB range (see NFR-1).
- A user can copy 50 different things over a day and reliably retrieve any of them from the tray popup.
- The app survives logout/login and reboot without losing pinned items.
- A junior dev unfamiliar with the codebase can complete a single task from §8 without needing to ask what the rest of the system does.

---

## 2. Requirements

### 2.1 Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Automatically capture copied plain text, no user action required. |
| FR-2 | Automatically capture copied images. |
| FR-3 | Persist the last N unpinned items (default N=50, configurable) across restarts. |
| FR-4 | Clicking a history item copies it back to the system clipboard and closes the popup. |
| FR-5 | User can pin an item; pinned items are exempt from the history cap and shown in their own section. |
| FR-6 | User can delete a single history item. |
| FR-7 | User can clear all unpinned history in one action (with confirmation). |
| FR-8 | User can search/filter text history by substring. |
| FR-9 | User can attach a short tag/label to an entry. |
| FR-10 | "Private mode" toggle pauses capture without quitting the app. |
| FR-11 | A tray icon opens the history popup on click. |
| FR-12 | The app ships a valid `.desktop` file so it can optionally be pinned to the GNOME Dock as a second trigger. |
| FR-13 | App can auto-start on login, toggleable from Settings. |

### 2.2 Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Idle memory footprint in the tens-of-MB range, not hundreds — this is why Electron was ruled out. |
| NFR-2 | Idle CPU from clipboard polling stays negligible (well under 1% average). |
| NFR-3 | Must work on the default Ubuntu 24.04 Wayland session — must not require the user to switch to an X11 session. |
| NFR-4 | No network calls, no telemetry. All data stays on the local machine. |
| NFR-5 | Storage uses plain, inspectable formats (SQLite + JSON), not a proprietary blob. |
| NFR-6 | Single-instance enforcement — launching the app a second time (e.g. via the Dock icon) must activate the existing instance, not spawn a duplicate. |

### 2.3 Constraints & environment
- OS: Ubuntu 24.04.x, GNOME Shell 46, Mutter compositor, **Wayland session by default**.
- Ubuntu ships the "AppIndicator and KStatusNotifierItem Support" Shell extension enabled out of the box — tray icons work with zero extra setup.
- GNOME's Mutter does **not** implement the `wlr-data-control` Wayland protocol that background clipboard managers normally rely on (this is a deliberate GNOME decision, not a bug — see §3.4). This is the single most important constraint in this document; read §3.4 before touching Phase 2.

---

## 3. System architecture

### 3.1 Component overview

```
 Other apps' clipboard                    Tray icon click / Dock icon
         |                                       |
         v                                       v
 +-------------------------------------------------------+
 |              Clipboard manager (one Python process)    |
 |  +--------------+   +-----------+   +---------------+ |
 |  |   Watcher    |-->|  Storage  |<->|   Popup UI    | |
 |  | reads clip-  |   | SQLite +  |   | search, pin,  | |
 |  | board, hashes|   | image     |   | copy, delete  | |
 |  | + de-dupes   |   | files     |   |               | |
 |  +--------------+   +-----------+   +---------------+ |
 +-------------------------------------------------------+
                                              |
                                              v
                                   Sets system clipboard
```

Five components, each a separate Python module (see §3.5):

- **Watcher** (`watcher.py`) — polls the clipboard on a timer, de-dupes, hands new entries to Storage. Pauses when Private mode is on.
- **Storage** (`storage.py`) — SQLite-backed CRUD layer. The only module that touches the database or the image cache directory. Nothing else talks to SQLite directly.
- **Tray** (`tray.py`) — the AppIndicator icon and its right-click menu. Left-click/activate toggles the Popup.
- **Popup UI** (`popup/`) — the borderless window shown on tray click. Reads from and writes to Storage; tells the Watcher to set the system clipboard when a row is clicked.
- **App shell** (`app.py`) — `Gtk.Application` subclass wiring the above together, handling single-instance activation (NFR-6) and the GLib main loop.

### 3.2 Data flow — user copies something
1. User copies text or an image in any app.
2. Watcher's timer (`GLib.timeout_add`, default every 750ms) reads the current clipboard contents.
3. Watcher hashes the content and compares it to the hash of the most recent entry; identical content is skipped (no duplicate rows for repeated copies of the same thing).
4. If new, Watcher calls `storage.add_entry(...)`. For images, Storage writes the full image and a thumbnail to disk and stores the paths; for text, the text is stored inline.
5. Storage runs a trim pass: if unpinned row count exceeds the configured cap, the oldest unpinned rows (and their image files) are deleted.

### 3.3 Data flow — user opens history and copies an item back
1. User clicks the tray icon (or the Dock launcher).
2. App shell's `activate` handler toggles the Popup window.
3. Popup calls `storage.get_recent()` and `storage.get_pinned()` to populate the list.
4. User clicks a row. Popup calls `watcher.set_clipboard_text(...)` or `set_clipboard_image(...)`, then hides itself.
5. The system clipboard now holds that content; user pastes into whatever app they want.

### 3.4 The Wayland clipboard access strategy — read this before Phase 2
GNOME's Mutter compositor does not implement `wlr-data-control`, the Wayland protocol extension that lets a background process read the clipboard without holding keyboard focus. This is by design (GNOME's stated reasoning is privacy — an unfocused app silently reading every clipboard change is a real concern). wlroots-based compositors (Sway, Hyprland) and KDE support it; GNOME does not, and almost certainly will not.

The practical, widely-used fix (the same one CopyQ documents and ships) is to run the app as an **XWayland client** instead of a native Wayland client, since Mutter bridges clipboard ownership between native Wayland apps and XWayland apps for compatibility. As an XWayland client, the app gets the traditional X11 clipboard model, where any client can query the current selection at any time regardless of focus — exactly what a clipboard manager needs.

**Decision for v1:** launch the whole app with `GDK_BACKEND=x11` set, forcing it into XWayland mode. This is a one-line change in the launcher (`.desktop` `Exec=` line and/or a wrapper script) — no code branches needed.

**Known trade-off:** CopyQ's own docs note that XWayland-mode clipboard monitoring can occasionally misbehave (e.g. around window-close edge cases). If this causes real problems in practice, the documented fallback is a small companion GNOME Shell extension that does the actual clipboard listening (Shell has privileged access) and relays new content to the app over D-Bus. That's explicitly out of scope for v1 (see §12) but flagged here so whoever hits the issue doesn't have to rediscover this.

**Do not build a native-Wayland-only watcher.** It will appear to work while the popup window has focus and silently stop capturing anything the moment focus moves elsewhere — this is the failure mode that makes the issue easy to miss in casual testing.

### 3.5 Repository layout

```
clipboard-manager/
├── pyproject.toml
├── README.md
├── clipboard_manager/
│   ├── __init__.py
│   ├── __main__.py        # entry point, GDK_BACKEND=x11 guard, starts Gtk.Application
│   ├── app.py              # Gtk.Application subclass, single-instance wiring
│   ├── watcher.py
│   ├── storage.py
│   ├── models.py           # ClipEntry dataclass
│   ├── config.py
│   ├── tray.py
│   ├── popup/
│   │   ├── __init__.py
│   │   ├── window.py        # PopupWindow shell, positioning, show/hide
│   │   ├── row.py           # single history row widget
│   │   └── search.py        # search entry + filter wiring
│   └── utils/
│       ├── logger.py
│       └── hashing.py
├── data/
│   └── icons/
│       └── clipboard-manager.svg
├── packaging/
│   ├── clipboard-manager.desktop
│   └── clipboard-manager.service   # systemd --user unit, optional
└── tests/
    └── test_storage.py
```

---

## 4. Technology stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.12 | Ships with Ubuntu 24.04; fastest iteration loop for matching the target UI. |
| GUI toolkit | GTK3 via PyGObject | The tray/indicator ecosystem (`AyatanaAppIndicator3`) targets GTK3; this is GNOME's own officially supported binding. |
| Tray icon | `AyatanaAppIndicator3` (gi typelib) | Standard SNI/AppIndicator implementation, packaged for Ubuntu 24.04 as `gir1.2-ayatanaappindicator3-0.1`. |
| Image handling | `GdkPixbuf` | Built into the GTK stack, no extra dependency. |
| Storage | SQLite (`sqlite3` stdlib) + flat image files | Zero-dependency, inspectable, easy to back up. |
| Config | JSON file | Avoids needing to compile/install a GSettings schema for a single-user app. |
| Packaging | `.desktop` autostart entry, optional systemd `--user` unit | Standard Linux desktop app patterns. |

**System packages to install (apt):**
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0
```

**Python packages:** none beyond the standard library for v1. PyGObject comes from the system `python3-gi` package, not pip — do not `pip install PyGObject` inside a venv unless you also install the matching system dev headers; simplest is to *not* use a venv for this project and rely on the system Python + system gi bindings.

---

## 5. Data model

### 5.1 SQLite schema (`storage.py` creates this on first run)

```sql
CREATE TABLE IF NOT EXISTS clip_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL CHECK(type IN ('text', 'image')),
    content     TEXT,              -- text content; NULL for images
    image_path  TEXT,              -- full image file path; NULL for text
    thumb_path  TEXT,              -- thumbnail file path; NULL for text
    created_at  TEXT NOT NULL,     -- ISO-8601 timestamp
    pinned      INTEGER NOT NULL DEFAULT 0,
    tag         TEXT,
    hash        TEXT NOT NULL      -- sha256 of content/image bytes, for de-dup
);

CREATE INDEX IF NOT EXISTS idx_clip_items_hash    ON clip_items(hash);
CREATE INDEX IF NOT EXISTS idx_clip_items_pinned  ON clip_items(pinned);
CREATE INDEX IF NOT EXISTS idx_clip_items_created ON clip_items(created_at);
```

### 5.2 Filesystem layout

```
~/.local/share/clipboard-manager/
├── history.db
└── images/
    ├── <uuid>.png          # full image
    └── <uuid>_thumb.png    # ~128px preview

~/.config/clipboard-manager/
└── config.json

~/.config/autostart/
└── clipboard-manager.desktop   # only present if autostart is enabled
```

Use `~/.local/share/...` (XDG data dir), **not** `~/.cache/...`, for the database and images — cache directories are fair game for cleanup tools, and a "permanently pinned" item disappearing because something cleared the cache would be a real data-loss bug.

### 5.3 Config file schema

```json
{
  "history_limit": 50,
  "poll_interval_ms": 750,
  "popup_corner": "top-right",
  "autostart_enabled": true,
  "private_mode": false,
  "max_image_size_mb": 8
}
```

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `history_limit` | int | 50 | Max unpinned rows kept; older ones trimmed. |
| `poll_interval_ms` | int | 750 | Clipboard polling interval. |
| `popup_corner` | string | `"top-right"` | One of `top-right`, `top-left`, `bottom-right`, `bottom-left`. |
| `autostart_enabled` | bool | true | Controls presence of the autostart `.desktop` file. |
| `private_mode` | bool | false | Persisted so the toggle survives a restart. |
| `max_image_size_mb` | int | 8 | Clipboard images larger than this are ignored (not stored), to bound disk usage. |

---

## 6. Module interfaces (contracts)

These signatures are the contract between modules. Implement exactly this; if a task needs something not listed here, add it here first, then implement it — don't let interfaces drift implicitly.

### 6.1 `models.py`
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ClipEntry:
    id: int
    type: str               # "text" | "image"
    content: Optional[str]
    image_path: Optional[str]
    thumb_path: Optional[str]
    created_at: datetime
    pinned: bool
    tag: Optional[str]
    hash: str
```

### 6.2 `storage.py`
```python
def init_db(db_path: str) -> None: ...
def add_entry(content: str | None, image_bytes: bytes | None, content_type: str) -> int:
    """Returns the new row id. Handles hashing, de-dup against the most recent
    entry, image file writing + thumbnail generation, and the trim pass."""

def get_recent(limit: int = 50) -> list[ClipEntry]: ...
def get_pinned() -> list[ClipEntry]: ...
def pin_entry(entry_id: int) -> None: ...
def unpin_entry(entry_id: int) -> None: ...
def delete_entry(entry_id: int) -> None: ...
def clear_history(keep_pinned: bool = True) -> None: ...
def search(query: str) -> list[ClipEntry]: ...
def set_tag(entry_id: int, tag: str | None) -> None: ...
def trim_history(max_unpinned: int) -> None: ...
```

### 6.3 `watcher.py`
```python
class ClipboardWatcher:
    def __init__(self, on_new_entry: Callable[[ClipEntry], None], poll_interval_ms: int = 750): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_private_mode(self, enabled: bool) -> None: ...
    def set_clipboard_text(self, text: str) -> None: ...
    def set_clipboard_image(self, image_path: str) -> None: ...
```

### 6.4 `tray.py`
```python
class TrayIcon:
    def __init__(self, on_activate: Callable[[], None]): ...
    """on_activate fires on left-click; right-click menu (Quit/Settings/About)
    is built internally."""
```

### 6.5 `popup/window.py`
```python
class PopupWindow(Gtk.Window):
    def toggle(self) -> None: ...
    def refresh(self) -> None: ...
    """Re-reads storage.get_recent()/get_pinned() and rebuilds the row list."""
```

### 6.6 `config.py`
```python
DEFAULT_CONFIG = {
    "history_limit": 50,
    "poll_interval_ms": 750,
    "popup_corner": "top-right",
    "autostart_enabled": True,
    "private_mode": False,
    "max_image_size_mb": 8,
}
def load_config() -> dict: ...
def save_config(cfg: dict) -> None: ...
```

---

## 7. UI specification

### 7.1 Popup window
- Undecorated `Gtk.Window`, skip-taskbar, always-on-top, width ~420px, max height ~600px (scrollable beyond that).
- Position anchored to a screen corner per `config.popup_corner` (default top-right) — there is no reliable cross-desktop API to get the exact tray icon pixel position on Wayland, so corner-anchoring is the deliberate choice, not a placeholder.
- Closes on focus-loss and on `Escape`.

### 7.2 Row anatomy
```
[ thumbnail or text preview, truncated ]   [edit] [pin] [copy] [tag] [x]
```
- Text rows show up to ~60 characters with ellipsis. Image rows show a small thumbnail.
- Action icons are hover-revealed (hidden until mouse-over the row) to keep the list visually quiet, matching the reference screenshot.
- Clicking anywhere on the row text/thumbnail (not on an icon) = same as clicking copy.

### 7.3 Layout / sections, top to bottom
1. `Gtk.SearchEntry` (filters by substring as you type).
2. Pinned items (if any).
3. Separator.
4. Recent history (most recent first), capped at `history_limit`.
5. Separator.
6. Private mode toggle row (switch).
7. Settings row.
8. Clear history row.

### 7.4 Icon mapping

| Action | Icon name |
|--------|-----------|
| Edit text | `document-edit-symbolic` |
| Pin / unpin | `view-pin-symbolic` (fallback: custom SVG asset if not in the icon theme) |
| Copy / paste back | `edit-copy-symbolic` |
| Tag | `tag-symbolic` |
| Delete | `edit-delete-symbolic` |

### 7.5 Confirmations
- Deleting a single row: no confirmation (low cost, easily re-copied if it's still on screen somewhere).
- "Clear history": confirmation dialog, since it's irreversible for unpinned items.

---

## 8. Task breakdown

### 8.0 Conventions
- IDs are `TASK-<phase><seq>`, e.g. `TASK-101` = Phase 1, task 1.
- **Definition of done for every task** (not repeated per row): implementation matches the interface in §6 exactly; manually exercised against the "Done when" column; no unhandled exceptions in the terminal during the happy path.
- Effort: S (under 1h), M (1–3h), L (half day+).

### 8.1 Phase 0 — Environment & scaffolding

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-001 | Confirm session type, GNOME version, and that the AppIndicator Shell extension is enabled. | — | — | `echo $XDG_SESSION_TYPE` and `gnome-extensions list` both checked and recorded in README. | S |
| TASK-002 | Install system dependencies from §4. | TASK-001 | — | `python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')"` runs without error. | S |
| TASK-003 | Scaffold the repository per §3.5 (empty modules, `pyproject.toml`, `.gitignore`). | TASK-002 | whole tree | `python -m clipboard_manager` runs and exits cleanly (even if it does nothing yet). | S |
| TASK-004 | Build a throwaway "hello tray icon" using `AyatanaAppIndicator3` to prove the icon renders in the Ubuntu top bar. | TASK-003 | `tray.py` (temporary script ok) | Icon visible in the top bar; clicking it logs to console. | S |
| TASK-005 | Add `utils/logger.py` — a single configured logger used by every other module. | TASK-003 | `utils/logger.py` | Calling `get_logger(__name__).info(...)` from two different modules produces consistently formatted output. | S |

### 8.2 Phase 1 — Data layer

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-101 | Implement `init_db()` creating the schema from §5.1 if it doesn't exist. | TASK-003 | `storage.py` | Running it twice in a row doesn't error and doesn't duplicate tables. | S |
| TASK-102 | Implement `add_entry()` for text, including hashing (sha256) and de-dup against the most recent row. | TASK-101 | `storage.py`, `utils/hashing.py` | Adding the same text twice in a row results in one row, not two. | M |
| TASK-103 | Extend `add_entry()` for images: write full image + thumbnail to `~/.local/share/clipboard-manager/images/`, respect `max_image_size_mb`. | TASK-102 | `storage.py` | A 2MB test PNG is stored with both a full and thumb file; a 20MB test image is rejected (not stored, no crash). | M |
| TASK-104 | Implement `get_recent()` and `get_pinned()`. | TASK-101 | `storage.py` | Returns `ClipEntry` objects per §6.1, most-recent-first. | S |
| TASK-105 | Implement `pin_entry()`, `unpin_entry()`, `delete_entry()`. | TASK-101 | `storage.py` | Pinned items don't appear in `get_recent()`'s trim-eligible set; deleted image rows also delete their files from disk. | M |
| TASK-106 | Implement `clear_history(keep_pinned=True)`. | TASK-105 | `storage.py` | After calling it, `get_recent()` is empty and `get_pinned()` is unchanged; corresponding image files are removed from disk. | S |
| TASK-107 | Implement `search(query)` — substring match over `content` and `tag`. | TASK-104 | `storage.py` | Case-insensitive substring search returns expected subset on a seeded test DB. | S |
| TASK-108 | Implement `set_tag()`. | TASK-101 | `storage.py` | Tag is set/cleared and reflected in `search()`. | S |
| TASK-109 | Implement `trim_history(max_unpinned)`, called automatically at the end of `add_entry()`. | TASK-105 | `storage.py` | Seeding 60 unpinned rows with a cap of 50 leaves exactly 50, oldest-first removed, and their image files deleted. | M |
| TASK-110 | Write `tests/test_storage.py` (pytest, no GTK import — pure data layer) covering TASK-102 through TASK-109. | TASK-109 | `tests/test_storage.py` | `pytest tests/test_storage.py` passes. | M |

### 8.3 Phase 2 — Clipboard watcher

**Read §3.4 before starting this phase.**

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-201 | Implement a function that reads the current clipboard's text and image content via `Gtk.Clipboard`. | TASK-002 | `watcher.py` | Running under `GDK_BACKEND=x11`, copying text in a terminal and re-running the read function reflects the new content. | M |
| TASK-202 | Wrap TASK-201 in `ClipboardWatcher` with a `GLib.timeout_add` poll loop at `poll_interval_ms`. | TASK-201 | `watcher.py` | Copying five different things in a row, each gets logged exactly once (no dupes, no misses) over a 10-second manual test. | M |
| TASK-203 | Wire the watcher's new-entry callback to `storage.add_entry()`. | TASK-202, TASK-103 | `watcher.py` | New clipboard content appears as a row in `history.db` within one poll interval. | S |
| TASK-204 | Implement `set_private_mode()` — when enabled, the poll loop still runs but skips calling `add_entry`. | TASK-202 | `watcher.py` | Toggling it off via a quick test script stops new rows from appearing even though clipboard content keeps changing. | S |
| TASK-205 | Implement `set_clipboard_text()` / `set_clipboard_image()` (the "paste back" direction). | TASK-201 | `watcher.py` | Calling it, then pasting (Ctrl+V) into a text editor / image-aware app, shows the expected content. | M |
| TASK-206 | Build a small CLI harness (`python -m clipboard_manager.watcher --debug`) that runs the watcher headlessly and prints every captured entry — for validating Phase 2 without the UI. | TASK-203 | `watcher.py` | Leaving it running for a few minutes while using the machine normally produces a sane, de-duped log. | S |

### 8.4 Phase 3 — Tray icon & app shell

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-301 | Implement `app.py` as a `Gtk.Application` subclass with a unique application ID, satisfying NFR-6. | TASK-003 | `app.py` | Launching the app twice from two terminals results in only one process and one tray icon. | M |
| TASK-302 | Create the app icon asset (simple SVG, clipboard glyph). | TASK-003 | `data/icons/clipboard-manager.svg` | Icon renders cleanly at both 16px and 48px. | S |
| TASK-303 | Implement `TrayIcon` per §6.4, with a right-click menu (Quit, Settings placeholder, About). | TASK-301, TASK-302 | `tray.py` | Icon shows in the top bar; right-click menu items respond; Quit cleanly exits the process. | M |
| TASK-304 | Wire tray left-click/`activate` to a placeholder popup toggle (can be an empty window for now). | TASK-303 | `app.py`, `tray.py` | Clicking the tray icon shows/hides an empty window. | S |

### 8.5 Phase 4 — Popup UI core

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-401 | Implement `PopupWindow` shell per §7.1: undecorated, skip-taskbar, corner-anchored positioning, hide on focus-loss/Escape. | TASK-304 | `popup/window.py` | Window appears in the configured corner, disappears on Escape and on clicking elsewhere. | M |
| TASK-402 | Implement the scrollable list container inside the popup. | TASK-401 | `popup/window.py` | A list of 60 placeholder rows scrolls smoothly without resizing the window past ~600px height. | S |
| TASK-403 | Implement the row widget per §7.2 (text/thumbnail + hover-revealed action icons). | TASK-402 | `popup/row.py` | Hovering a row reveals the 5 action icons from §7.4; they're hidden otherwise. | M |
| TASK-404 | Wire the copy action: clicking row text/thumbnail calls `watcher.set_clipboard_*()` then hides the popup. | TASK-403, TASK-205 | `popup/row.py`, `popup/window.py` | Clicking a history row results in that content being on the system clipboard and the popup closing. | M |
| TASK-405 | Wire the delete action to `storage.delete_entry()` + `refresh()`. | TASK-403, TASK-105 | `popup/row.py` | Clicking the x icon removes the row immediately, no popup flicker/full rebuild lag. | S |
| TASK-406 | Wire the pin action to `storage.pin_entry()`/`unpin_entry()` + `refresh()`, moving the item to the pinned section. | TASK-403, TASK-105 | `popup/row.py` | Pinning an item moves it above the separator; unpinning moves it back. | M |
| TASK-407 | Implement the pinned/history section split and separator per §7.3. | TASK-406 | `popup/window.py` | Pinned items always render above the separator regardless of recency. | S |
| TASK-408 | Implement `refresh()` fully: re-query storage and rebuild the visible list, preserving scroll position if possible. | TASK-402–407 | `popup/window.py` | Opening the popup after copying something new shows it at the top of the recent section without a visible jump. | M |

### 8.6 Phase 5 — Search, tags, edit

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-501 | Add `Gtk.SearchEntry` at the top of the popup, wired to `storage.search()`, filtering the list live as the user types. | TASK-408, TASK-107 | `popup/search.py`, `popup/window.py` | Typing a substring narrows the list within one keystroke's latency; clearing the field restores the full list. | M |
| TASK-502 | Add a tag pill on rows that have one (per §7.2), plus a small inline entry to add/edit a tag. | TASK-403, TASK-108 | `popup/row.py` | Setting a tag persists across a popup close/reopen. | M |
| TASK-503 | Add an "edit text" dialog for text-type rows, saving back via a new `storage.update_content()` (add this function to §6.2 contract before implementing). | TASK-403 | `popup/row.py`, `storage.py` | Editing a row's text updates `history.db` and the visible row without creating a duplicate entry. | M |
| TASK-504 | Add keyboard navigation inside the popup (Up/Down to move selection, Enter to copy the selected row, Escape to close). | TASK-408 | `popup/window.py` | Full mouse-free flow: open popup, arrow to an item, Enter, content is on the clipboard. | M |

### 8.7 Phase 6 — Settings & private mode

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-601 | Implement `config.py` per §6.6 — load with defaults, save, atomic write. | TASK-003 | `config.py` | Deleting `config.json` and restarting regenerates it with defaults; editing a value by hand and restarting picks it up. | S |
| TASK-602 | Build the Settings dialog (history limit, poll interval, popup corner, autostart toggle). | TASK-601, TASK-303 | `popup/` (new `settings_dialog.py`) | Changing history limit in the dialog and saving actually changes trim behavior on the next clipboard copy. | M |
| TASK-603 | Add the Private mode toggle row to the popup footer (§7.3), wired to `watcher.set_private_mode()` and persisted in config. | TASK-204, TASK-601 | `popup/window.py` | Toggling it in the UI, then restarting the app, the toggle remembers its last state. | S |
| TASK-604 | Add the "Clear history" footer row with confirmation dialog, wired to `storage.clear_history()`. | TASK-106 | `popup/window.py` | Confirming clears all unpinned rows and files; canceling does nothing. | S |
| TASK-605 | Implement autostart toggle logic: writing/removing `~/.config/autostart/clipboard-manager.desktop` based on `config.autostart_enabled`. | TASK-601 | `config.py` or new `autostart.py` | Toggling it on creates the file with correct `Exec=`/`GDK_BACKEND=x11`; toggling off removes it. | S |

### 8.8 Phase 7 — Packaging, docs, QA

| ID | Task | Depends on | Files | Done when | Effort |
|----|------|------------|-------|-----------|--------|
| TASK-701 | Author the production `.desktop` launcher (correct `Name`, `Icon`, `Exec=env GDK_BACKEND=x11 ...`, `StartupNotify=false`). | TASK-301, TASK-302 | `packaging/clipboard-manager.desktop` | App grid shows the icon/name correctly; "Add to Favorites" pins it to the Dock and it launches/activates correctly. | S |
| TASK-702 | (Optional) Author a systemd `--user` unit as an alternative to autostart, with auto-restart on crash. | TASK-701 | `packaging/clipboard-manager.service` | `systemctl --user enable --now clipboard-manager` starts the app; killing the process causes systemd to restart it. | S |
| TASK-703 | Write the README: install steps, run instructions, uninstall steps. | all prior | `README.md` | A teammate with a clean Ubuntu 24.04 machine can follow it start-to-finish with no questions. | M |
| TASK-704 | Run the manual QA checklist from §9.2 end-to-end and log results. | all prior | — | Every row in the checklist passes. | M |
| TASK-705 | Measure idle resource usage against NFR-1/NFR-2. | TASK-704 | — | `ps -o rss,pcpu -p <pid>` over a 10-minute idle period meets the targets in §9.3. | S |
| TASK-706 | Visual polish pass: dark-theme styling (Yaru-dark) for the popup, consistent icon sizes, spacing per the reference screenshot. | TASK-408 | `popup/*.py` | Side-by-side with the reference screenshot, layout and spacing are visually consistent in both light and dark GNOME themes. | M |

---

## 9. Testing & QA

### 9.1 Automated
- `tests/test_storage.py` (TASK-110) is the only automated suite for v1, since it's the one layer with no GTK/display dependency and therefore runs in CI without a display server.

### 9.2 Manual QA checklist

| Scenario | Expected result |
|----------|------------------|
| Copy plain text in a browser | Appears at the top of the popup's recent list within ~1s. |
| Copy a screenshot/image | Appears as a thumbnail row. |
| Copy the same text twice in a row | Only one row, not two. |
| Pin an item, copy 60 more things | Pinned item still present; unpinned list capped at `history_limit`. |
| Click a row | Content is set on the system clipboard; popup closes. |
| Delete a row | Row disappears immediately. |
| Search for a substring | List narrows correctly; clearing search restores full list. |
| Toggle Private mode, copy something | Nothing new appears in history until toggled back off. |
| Clear history | All unpinned rows gone; pinned rows untouched. |
| Quit and relaunch the app | Pinned items and config persist; tray icon reappears. |
| Launch the app a second time | No duplicate tray icon or process (NFR-6). |
| Log out and back in | App auto-starts if enabled. |

### 9.3 Resource usage targets
- Idle RSS memory: target under 60MB (stretch: under 40MB).
- Idle CPU: effectively 0% between polls, brief negligible spikes only during a poll tick.
- Measure with: `ps -o rss,pcpu -p $(pgrep -f clipboard_manager)`.

---

## 10. Deployment / installation guide

```bash
# 1. System dependencies
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0

# 2. Clone / copy the repo, then run directly (no venv needed — see §4)
cd clipboard-manager
python3 -m clipboard_manager

# 3. Enable autostart (writes ~/.config/autostart/clipboard-manager.desktop)
#    Toggle this from the Settings dialog (TASK-602/605), or manually:
cp packaging/clipboard-manager.desktop ~/.config/autostart/

# 4. (Optional) Run as a systemd user service instead of autostart
cp packaging/clipboard-manager.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now clipboard-manager
```

**Uninstall:**
```bash
systemctl --user disable --now clipboard-manager 2>/dev/null
rm -f ~/.config/autostart/clipboard-manager.desktop
rm -f ~/.config/systemd/user/clipboard-manager.service
rm -rf ~/.local/share/clipboard-manager ~/.config/clipboard-manager
```

---

## 11. Risks & open decisions

| Risk | Impact | Mitigation |
|------|--------|------------|
| XWayland-mode clipboard monitoring edge cases (per §3.4) | Watcher misses or duplicates a capture in rare cases | Documented fallback: companion GNOME Shell extension + D-Bus relay (out of scope for v1, see §12). |
| No public API for exact tray icon screen position | Popup can't be pixel-perfectly anchored to the icon | Corner-anchoring (configurable) instead — acceptable UX trade-off. |
| Large images copied repeatedly | Disk usage growth | `max_image_size_mb` cap (§5.3) + `trim_history` (TASK-109). |
| Multi-monitor setups | Corner anchoring may pick the wrong monitor | v1 anchors to the primary monitor only; flag as a known limitation in README. |

---

## 12. Out of scope for v1 (future enhancements)
- Global keyboard shortcut (would need a GNOME custom-keybinding registered via `gsettings`, since Wayland doesn't allow apps to grab hotkeys directly).
- GNOME Shell extension companion for fully native Wayland clipboard access (only needed if the XWayland approach proves unreliable in practice).
- Encryption-at-rest for sensitive clipboard entries.
- Rich text / HTML clipboard format preservation.
- Packaging as a `.deb` or Flatpak for wider distribution.

---

## 13. Glossary
- **SNI** — StatusNotifierItem, the D-Bus protocol modern Linux tray icons use.
- **AppIndicator** — the library/typelib implementing SNI that this project uses for the tray icon.
- **XWayland** — the compatibility layer that lets X11 apps run inside a Wayland session.
- **wlr-data-control** — a Wayland protocol extension for background clipboard access, supported by wlroots/KDE compositors but not by GNOME's Mutter.
