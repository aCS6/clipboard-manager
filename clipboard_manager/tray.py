"""Tray icon using Gtk.StatusIcon — supports real left-click activation."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

from clipboard_manager.utils.logger import get_logger

log = get_logger(__name__)

_ICON_PATH = str(Path(__file__).parent.parent / "data" / "icons" / "clipboard-manager.svg")


class TrayIcon:
    def __init__(
        self,
        on_open_popup: Callable[[], None],
        on_settings: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_open_popup = on_open_popup

        self._icon = Gtk.StatusIcon()
        # Load SVG as pixbuf so it works reliably
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(_ICON_PATH, 22, 22)
            self._icon.set_from_pixbuf(pb)
        except Exception:
            self._icon.set_from_icon_name("edit-paste")
        self._icon.set_tooltip_text("Clipboard Manager")
        self._icon.set_visible(True)

        # Left-click → open popup
        self._icon.connect("activate", lambda *_: on_open_popup())

        # Right-click → small context menu
        self._icon.connect("popup-menu", self._on_popup_menu)

        # Build context menu once
        self._menu = Gtk.Menu()

        open_item = Gtk.MenuItem(label="Open History")
        open_item.connect("activate", lambda *_: on_open_popup())
        self._menu.append(open_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        settings_item = Gtk.MenuItem(label="Settings")
        if on_settings:
            settings_item.connect("activate", lambda *_: on_settings())
        else:
            settings_item.set_sensitive(False)
        self._menu.append(settings_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: (on_quit() if on_quit else Gtk.main_quit()))
        self._menu.append(quit_item)

        self._menu.show_all()
        log.info("Tray icon initialised (StatusIcon)")

    def _on_popup_menu(self, icon, button, time) -> None:
        self._menu.popup(None, None, Gtk.StatusIcon.position_menu,
                         icon, button, time)

    def mark_dirty(self) -> None:
        pass  # popup refreshes on show
