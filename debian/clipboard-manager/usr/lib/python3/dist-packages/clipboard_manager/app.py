"""Gtk.Application subclass — wires watcher, storage, tray and popup together."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from clipboard_manager import storage
from clipboard_manager.config import load_config, save_config
from clipboard_manager.models import ClipEntry
from clipboard_manager.utils.logger import get_logger
from clipboard_manager.watcher import ClipboardWatcher
from clipboard_manager.tray import TrayIcon

log = get_logger(__name__)

APP_ID = "com.github.aCS6.ClipboardManager"


class ClipboardManagerApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._cfg: dict = {}
        self._watcher: ClipboardWatcher | None = None
        self._tray: TrayIcon | None = None
        self._popup = None  # PopupWindow, created lazily

    # ------------------------------------------------------------------ #
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self._cfg = load_config()
        storage.init_db()
        log.info("App startup complete")

    def do_activate(self) -> None:
        """Called on first launch and on subsequent activate signals (second instance)."""
        if self._watcher is None:
            self._start_watcher()
            self._tray = TrayIcon(
                on_open_popup=self._toggle_popup,
                on_settings=self._open_settings,
                on_quit=self.quit,
            )
            self._build_popup()
        else:
            # Second instance — just show the popup
            self._toggle_popup()

    # ------------------------------------------------------------------ #
    def _start_watcher(self) -> None:
        self._watcher = ClipboardWatcher(
            on_new_entry=self._on_new_entry,
            poll_interval_ms=self._cfg["poll_interval_ms"],
            max_image_size_mb=self._cfg["max_image_size_mb"],
            history_limit=self._cfg["history_limit"],
        )
        self._watcher.set_private_mode(self._cfg["private_mode"])
        self._watcher.start()

    def _build_popup(self) -> None:
        from clipboard_manager.popup.window import PopupWindow
        self._popup = PopupWindow(self._watcher, self._cfg)
        self.add_window(self._popup)

    def _toggle_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        self._popup.toggle()

    def _open_settings(self) -> None:
        from clipboard_manager.popup.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._cfg, parent=self._popup)
        if dlg.run() == Gtk.ResponseType.OK:
            self._cfg = dlg.get_config()
            save_config(self._cfg)
            self._apply_config()
        dlg.destroy()

    def _apply_config(self) -> None:
        if self._watcher:
            self._watcher.set_private_mode(self._cfg["private_mode"])
        if self._popup:
            self._popup.cfg = self._cfg

    def _tray_copy(self, entry) -> None:
        if entry.type == "text" and entry.content:
            self._watcher.set_clipboard_text(entry.content)
        elif entry.type == "image" and entry.image_path:
            self._watcher.set_clipboard_image(entry.image_path)

    def _on_new_entry(self, entry) -> None:
        log.debug("New entry id=%d type=%s", entry.id, entry.type)
        if self._tray:
            self._tray.mark_dirty()
        # Don't refresh the popup mid-view — it will refresh on next open

    def do_shutdown(self) -> None:
        if self._watcher:
            self._watcher.stop()
        Gtk.Application.do_shutdown(self)
