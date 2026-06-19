"""Settings dialog."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from clipboard_manager.autostart import set_autostart


class SettingsDialog(Gtk.Dialog):
    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(title="Settings", parent=parent, flags=Gtk.DialogFlags.MODAL)
        self.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK,
                         Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self._cfg = dict(cfg)
        self._build()

    def _build(self) -> None:
        grid = Gtk.Grid(column_spacing=16, row_spacing=10)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)

        def lbl(text: str, row: int) -> None:
            l = Gtk.Label(label=text, xalign=1)
            l.get_style_context().add_class("dim-label")
            grid.attach(l, 0, row, 1, 1)

        lbl("History limit:", 0)
        self._history_limit = Gtk.SpinButton.new_with_range(10, 500, 10)
        self._history_limit.set_value(self._cfg.get("history_limit", 50))
        grid.attach(self._history_limit, 1, 0, 1, 1)

        lbl("Poll interval (ms):", 1)
        self._poll = Gtk.SpinButton.new_with_range(200, 5000, 100)
        self._poll.set_value(self._cfg.get("poll_interval_ms", 750))
        grid.attach(self._poll, 1, 1, 1, 1)

        lbl("Popup position:", 2)
        self._corner = Gtk.ComboBoxText()
        for opt, label in (
            ("top-right",    "Top right"),
            ("top-left",     "Top left"),
            ("bottom-right", "Bottom right"),
            ("bottom-left",  "Bottom left"),
        ):
            self._corner.append(opt, label)
        self._corner.set_active_id(self._cfg.get("popup_corner", "top-right"))
        grid.attach(self._corner, 1, 2, 1, 1)

        # Autostart — CheckButton is the standard GTK idiom for a boolean setting
        self._autostart = Gtk.CheckButton(label="Start automatically on login")
        self._autostart.set_active(self._cfg.get("autostart_enabled", True))
        grid.attach(self._autostart, 0, 3, 2, 1)

        self.get_content_area().add(grid)
        self.show_all()

    def get_config(self) -> dict:
        cfg = dict(self._cfg)
        cfg["history_limit"] = int(self._history_limit.get_value())
        cfg["poll_interval_ms"] = int(self._poll.get_value())
        cfg["popup_corner"] = self._corner.get_active_id() or "top-right"
        cfg["autostart_enabled"] = self._autostart.get_active()
        set_autostart(cfg["autostart_enabled"])
        return cfg
