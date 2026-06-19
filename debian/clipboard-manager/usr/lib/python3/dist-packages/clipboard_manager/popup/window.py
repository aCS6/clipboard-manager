"""Popup window — TOPLEVEL, hides on focus-out/click-outside/Escape."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from clipboard_manager import storage
from clipboard_manager.models import ClipEntry
from clipboard_manager.popup.row import ClipRow
from clipboard_manager.utils.logger import get_logger

log = get_logger(__name__)

_WIDTH = 440
_MAX_HEIGHT = 520

_CSS = b"""
.popup-window {
    background-color: @theme_bg_color;
    border: 1px solid alpha(@theme_fg_color, 0.15);
    border-radius: 8px;
}
.section-label {
    font-size: 0.75em;
    font-weight: bold;
    color: alpha(@theme_fg_color, 0.5);
    padding: 4px 8px 2px 8px;
}
.clip-row {
    border-bottom: 1px solid alpha(@theme_fg_color, 0.08);
}
.clip-row:hover {
    background-color: alpha(@theme_selected_bg_color, 0.15);
}
.footer-bar {
    border-top: 1px solid alpha(@theme_fg_color, 0.12);
    padding: 4px 8px;
}
"""

_css_applied = False

def _apply_css() -> None:
    global _css_applied
    if _css_applied:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_applied = True


class PopupWindow(Gtk.Window):
    def __init__(self, watcher, cfg: dict) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._watcher = watcher
        self.cfg = cfg
        self._hiding = False  # guard against recursive hide

        _apply_css()

        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_default_size(_WIDTH, -1)
        self.set_resizable(False)
        self.get_style_context().add_class("popup-window")

        self._build_ui()

        # Hide on focus loss — TOPLEVEL windows receive focus events
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("key-press-event", self._on_key)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Scrollable list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(_MAX_HEIGHT)
        scroll.set_propagate_natural_height(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self._list_box)
        outer.pack_start(scroll, True, True, 0)

        # Footer
        footer = Gtk.Box(spacing=8)
        footer.get_style_context().add_class("footer-bar")

        self._priv_btn = Gtk.ToggleButton(label="Private mode: OFF")
        self._priv_btn.set_active(self.cfg.get("private_mode", False))
        self._priv_btn.set_relief(Gtk.ReliefStyle.NONE)
        self._priv_btn.get_style_context().add_class("flat")
        self._priv_btn.connect("toggled", self._on_private_toggle)
        footer.pack_start(self._priv_btn, False, False, 0)

        clear_btn = Gtk.Button(label="Clear all")
        clear_btn.set_relief(Gtk.ReliefStyle.NONE)
        clear_btn.get_style_context().add_class("flat")
        clear_btn.connect("clicked", self._on_clear)
        footer.pack_end(clear_btn, False, False, 0)

        outer.pack_start(Gtk.Separator(), False, False, 0)
        outer.pack_start(footer, False, False, 0)

        self.add(outer)

    # ------------------------------------------------------------------ #
    def toggle(self) -> None:
        if self.get_visible():
            self._do_hide()
        else:
            self._position()
            self.refresh()
            self.show_all()
            self.present()

    def _do_hide(self) -> None:
        if not self._hiding:
            self._hiding = True
            self.hide()
            self._hiding = False

    def _on_focus_out(self, window, event) -> bool:
        # Delay slightly so button clicks inside the window register first
        GLib.timeout_add(80, self._check_and_hide)
        return False

    def _check_and_hide(self) -> bool:
        if self.get_visible() and not self.has_toplevel_focus():
            self._do_hide()
        return False  # don't repeat

    def refresh(self) -> None:
        for child in self._list_box.get_children():
            self._list_box.remove(child)

        pinned = storage.get_pinned()
        recent = storage.get_recent(self.cfg.get("history_limit", 50))

        if pinned:
            self._add_label("📌 Pinned")
            for entry in pinned:
                self._list_box.add(ClipRow(
                    entry, self._do_copy, self._do_delete,
                    self._do_pin, self._do_tag, self._do_edit,
                ))
            self._list_box.add(_SepRow())

        if recent:
            if pinned:
                self._add_label("Recent")
            for entry in recent:
                self._list_box.add(ClipRow(
                    entry, self._do_copy, self._do_delete,
                    self._do_pin, self._do_tag, self._do_edit,
                ))
        elif not pinned:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            lbl = Gtk.Label(label="No clipboard history yet.")
            lbl.set_margin_top(16)
            lbl.set_margin_bottom(16)
            row.add(lbl)
            self._list_box.add(row)

        self._list_box.show_all()

    def _add_label(self, text: str) -> None:
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0)
        lbl.get_style_context().add_class("section-label")
        row.add(lbl)
        self._list_box.add(row)

    # ------------------------------------------------------------------ #
    def _do_copy(self, entry: ClipEntry) -> None:
        if entry.type == "text" and entry.content:
            self._watcher.set_clipboard_text(entry.content)
        elif entry.type == "image" and entry.image_path:
            self._watcher.set_clipboard_image(entry.image_path)
        self._do_hide()

    def _do_delete(self, entry: ClipEntry) -> None:
        storage.delete_entry(entry.id)
        # Remove just that row without full rebuild — no blink
        for child in self._list_box.get_children():
            if isinstance(child, ClipRow) and child.entry.id == entry.id:
                self._list_box.remove(child)
                break
        self._list_box.show_all()

    def _do_pin(self, entry: ClipEntry) -> None:
        if entry.pinned:
            storage.unpin_entry(entry.id)
        else:
            storage.pin_entry(entry.id)
        self.refresh()

    def _do_tag(self, entry: ClipEntry) -> None:
        self._hiding = True
        dlg = _TagDialog(entry.tag or "", parent=self)
        response = dlg.run()
        tag = dlg.get_tag()
        dlg.destroy()
        self._hiding = False
        if response == Gtk.ResponseType.OK:
            storage.set_tag(entry.id, tag or None)
            self.refresh()

    def _do_edit(self, entry: ClipEntry) -> None:
        if entry.type != "text":
            return
        self._hiding = True
        dlg = _EditDialog(entry.content or "", parent=self)
        response = dlg.run()
        text = dlg.get_text()
        dlg.destroy()
        self._hiding = False
        if response == Gtk.ResponseType.OK:
            storage.update_content(entry.id, text)
            self.refresh()

    def _on_private_toggle(self, btn) -> None:
        enabled = btn.get_active()
        btn.set_label("Private mode: ON" if enabled else "Private mode: OFF")
        self._watcher.set_private_mode(enabled)
        self.cfg["private_mode"] = enabled
        from clipboard_manager.config import save_config
        save_config(self.cfg)

    def _on_clear(self, *_) -> None:
        self._hiding = True  # prevent focus-out from hiding while dialog is open
        dlg = Gtk.MessageDialog(
            parent=self, flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format="Clear all unpinned history?",
        )
        response = dlg.run()
        dlg.destroy()
        self._hiding = False
        if response == Gtk.ResponseType.OK:
            storage.clear_history(keep_pinned=True)
            self.refresh()

    def _on_key(self, widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._do_hide()
            return True
        return False

    def _position(self) -> None:
        screen = Gdk.Screen.get_default()
        geo = screen.get_monitor_geometry(screen.get_primary_monitor())
        corner = self.cfg.get("popup_corner", "top-right")
        m = 8
        if corner == "top-right":
            self.move(geo.x + geo.width - _WIDTH - m, geo.y + m + 32)
        elif corner == "top-left":
            self.move(geo.x + m, geo.y + m + 32)
        elif corner == "bottom-right":
            self.move(geo.x + geo.width - _WIDTH - m, geo.y + geo.height - m - 400)
        else:
            self.move(geo.x + m, geo.y + geo.height - m - 400)


class _SepRow(Gtk.ListBoxRow):
    def __init__(self) -> None:
        super().__init__()
        self.set_selectable(False)
        self.add(Gtk.Separator())


class _TagDialog(Gtk.Dialog):
    def __init__(self, current: str, parent=None) -> None:
        super().__init__(title="Set tag", parent=parent, flags=Gtk.DialogFlags.MODAL)
        self.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK,
                         Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self._entry = Gtk.Entry()
        self._entry.set_text(current)
        self._entry.connect("activate", lambda *_: self.response(Gtk.ResponseType.OK))
        self.get_content_area().pack_start(self._entry, False, False, 8)
        self.show_all()

    def get_tag(self) -> str:
        return self._entry.get_text().strip()


class _EditDialog(Gtk.Dialog):
    def __init__(self, current: str, parent=None) -> None:
        super().__init__(title="Edit text", parent=parent, flags=Gtk.DialogFlags.MODAL)
        self.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK,
                         Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.set_default_size(400, 200)
        tv = Gtk.TextView()
        tv.get_buffer().set_text(current)
        tv.set_wrap_mode(Gtk.WrapMode.WORD)
        self._buffer = tv.get_buffer()
        sw = Gtk.ScrolledWindow()
        sw.add(tv)
        self.get_content_area().pack_start(sw, True, True, 4)
        self.show_all()

    def get_text(self) -> str:
        s, e = self._buffer.get_bounds()
        return self._buffer.get_text(s, e, True)
