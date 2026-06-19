"""Single history row: [icon] [content label] [delete btn] — click content = copy."""
from __future__ import annotations

from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

from clipboard_manager import storage
from clipboard_manager.models import ClipEntry


class ClipRow(Gtk.ListBoxRow):
    def __init__(
        self,
        entry: ClipEntry,
        on_copy: Callable[[ClipEntry], None],
        on_delete: Callable[[ClipEntry], None],
        on_pin_toggle: Callable[[ClipEntry], None],
        on_tag_edit: Callable[[ClipEntry], None],
        on_text_edit: Callable[[ClipEntry], None],
    ) -> None:
        super().__init__()
        self.entry = entry
        self._on_copy = on_copy
        self._on_delete = on_delete
        self._on_pin = on_pin_toggle
        self._on_tag = on_tag_edit
        self._on_edit = on_text_edit

        self.get_style_context().add_class("clip-row")
        self._build()

    def _build(self) -> None:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hbox.set_margin_start(6)
        hbox.set_margin_end(4)
        hbox.set_margin_top(5)
        hbox.set_margin_bottom(5)

        # Left: type icon
        if self.entry.type == "image":
            type_icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic", Gtk.IconSize.MENU)
        else:
            type_icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic", Gtk.IconSize.MENU)
        type_icon.set_margin_end(8)
        type_icon.get_style_context().add_class("dim-label")
        hbox.pack_start(type_icon, False, False, 0)

        # Middle: clickable content area
        if self.entry.type == "image" and self.entry.thumb_path:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.entry.thumb_path, 40, 40, True)
                content_widget = Gtk.Image.new_from_pixbuf(pb)
            except Exception:
                content_widget = Gtk.Label(label="[Image]")
        else:
            text = (self.entry.content or "").replace("\n", " ")
            content_widget = Gtk.Label(label=text)
            content_widget.set_xalign(0)
            content_widget.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            content_widget.set_max_width_chars(55)

        # Wrap in an EventBox so we can capture clicks on the content
        content_box = Gtk.EventBox()
        content_box.add(content_widget)
        content_box.connect("button-press-event", self._on_content_click)
        content_box.set_tooltip_text("Click to copy")
        hbox.pack_start(content_box, True, True, 0)

        # Tag pill (if set)
        if self.entry.tag:
            tag_lbl = Gtk.Label(label=f"#{self.entry.tag}")
            tag_lbl.get_style_context().add_class("dim-label")
            tag_lbl.set_margin_start(4)
            tag_lbl.set_margin_end(4)
            hbox.pack_start(tag_lbl, False, False, 0)

        # Right: delete button only
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_tooltip_text("Delete")
        btn.set_focus_on_click(False)
        btn.add(Gtk.Image.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.MENU))
        btn.connect("clicked", lambda *_, e=self.entry: self._on_delete(e))
        btn.get_style_context().add_class("flat")
        hbox.pack_end(btn, False, False, 0)

        self.add(hbox)
        self.show_all()

    def _on_content_click(self, widget, event) -> bool:
        if event.button == 1:
            self._on_copy(self.entry)
        return True
