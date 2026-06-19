"""Search entry widget — calls back with current query string on each keystroke."""
from __future__ import annotations

from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class SearchBar(Gtk.SearchEntry):
    def __init__(self, on_search: Callable[[str], None]) -> None:
        super().__init__()
        self.set_placeholder_text("Search history…")
        self.set_hexpand(True)
        self.connect("search-changed", lambda w: on_search(w.get_text()))
        self.connect("stop-search", lambda *_: self.set_text(""))
