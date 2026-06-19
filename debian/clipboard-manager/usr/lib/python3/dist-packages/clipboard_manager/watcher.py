"""Clipboard watcher — polls the clipboard via Gtk.Clipboard under GDK_BACKEND=x11."""
from __future__ import annotations

import io
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GLib, Gtk, Gdk, GdkPixbuf

from clipboard_manager import storage
from clipboard_manager.models import ClipEntry
from clipboard_manager.utils.logger import get_logger

log = get_logger(__name__)


class ClipboardWatcher:
    def __init__(
        self,
        on_new_entry: Callable[[ClipEntry], None],
        poll_interval_ms: int = 750,
        max_image_size_mb: int = 8,
        history_limit: int = 50,
    ) -> None:
        self._callback = on_new_entry
        self._interval = poll_interval_ms
        self._private = False
        self._timer_id: Optional[int] = None
        self._max_image_mb = max_image_size_mb
        self._history_limit = history_limit
        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

    def start(self) -> None:
        self._timer_id = GLib.timeout_add(self._interval, self._poll)
        log.info("Watcher started (interval=%dms)", self._interval)

    def stop(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        log.info("Watcher stopped")

    def set_private_mode(self, enabled: bool) -> None:
        self._private = enabled
        log.info("Private mode: %s", enabled)

    def set_clipboard_text(self, text: str) -> None:
        self._clipboard.set_text(text, -1)
        self._clipboard.store()

    def set_clipboard_image(self, image_path: str) -> None:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_path)
        self._clipboard.set_image(pixbuf)
        self._clipboard.store()

    # ------------------------------------------------------------------ #
    def _poll(self) -> bool:
        if self._private:
            return True  # keep timer alive, do nothing

        # Try text first
        text = self._clipboard.wait_for_text()
        if text:
            entry_id = storage.add_entry(
                content=text,
                image_bytes=None,
                content_type="text",
                max_image_size_mb=self._max_image_mb,
                history_limit=self._history_limit,
            )
            if entry_id > 0:
                self._emit(entry_id)
            return True

        # Try image
        pixbuf = self._clipboard.wait_for_image()
        if pixbuf:
            image_bytes = _pixbuf_to_png_bytes(pixbuf)
            if image_bytes:
                entry_id = storage.add_entry(
                    content=None,
                    image_bytes=image_bytes,
                    content_type="image",
                    max_image_size_mb=self._max_image_mb,
                    history_limit=self._history_limit,
                )
                if entry_id > 0:
                    self._emit(entry_id)

        return True  # keep GLib timer alive

    def _emit(self, entry_id: int) -> None:
        conn = storage._get_conn()
        row = conn.execute("SELECT * FROM clip_items WHERE id=?", (entry_id,)).fetchone()
        if row:
            entry = storage._row_to_entry(row)
            try:
                self._callback(entry)
            except Exception:
                log.exception("Error in on_new_entry callback")


def _pixbuf_to_png_bytes(pixbuf: GdkPixbuf.Pixbuf) -> Optional[bytes]:
    ok, buf = pixbuf.save_to_bufferv("png", [], [])
    return bytes(buf) if ok else None


# ------------------------------------------------------------------ #
# CLI harness: python -m clipboard_manager.watcher --debug
if __name__ == "__main__":
    import sys
    import os

    if os.environ.get("GDK_BACKEND") != "x11":
        os.environ["GDK_BACKEND"] = "x11"

    from clipboard_manager.config import load_config
    from clipboard_manager import storage as _storage

    cfg = load_config()
    _storage.init_db()

    def _on_entry(entry: ClipEntry) -> None:
        print(f"[NEW] id={entry.id} type={entry.type} "
              f"content={repr(entry.content[:60]) if entry.content else '<image>'}")

    watcher = ClipboardWatcher(
        on_new_entry=_on_entry,
        poll_interval_ms=cfg["poll_interval_ms"],
        max_image_size_mb=cfg["max_image_size_mb"],
        history_limit=cfg["history_limit"],
    )

    # We need a Gtk main loop to process clipboard requests
    Gtk.init(sys.argv)
    watcher.start()
    print("Watcher running — copy something (Ctrl+C to quit)")
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        watcher.stop()
