"""pytest test suite for the storage layer (no GTK dependency)."""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

# Patch image saving to avoid needing GdkPixbuf in CI
import clipboard_manager.storage as _storage_mod

_orig_save_image = _storage_mod._save_image


def _fake_save_image(image_bytes: bytes):
    uid = "test_" + str(len(image_bytes))
    full = _storage_mod._IMAGES_DIR / f"{uid}.png"
    thumb = _storage_mod._IMAGES_DIR / f"{uid}_thumb.png"
    full.write_bytes(image_bytes)
    thumb.write_bytes(image_bytes)
    return full, thumb


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own in-memory-like temp DB and images dir."""
    monkeypatch.setattr(_storage_mod, "_IMAGES_DIR", tmp_path / "images")
    (tmp_path / "images").mkdir()
    # Reset global connection
    monkeypatch.setattr(_storage_mod, "_conn", None)
    db = tmp_path / "test.db"
    _storage_mod.init_db(str(db))
    monkeypatch.setattr(_storage_mod, "_save_image", _fake_save_image)
    yield
    if _storage_mod._conn:
        _storage_mod._conn.close()
        _storage_mod._conn = None


# ------------------------------------------------------------------ #
def test_init_db_idempotent(tmp_path):
    """Running init_db twice on the same path should not raise."""
    db = tmp_path / "double.db"
    _storage_mod._conn = None
    _storage_mod.init_db(str(db))
    _storage_mod.init_db(str(db))  # second call — no error


def test_add_text_entry():
    eid = _storage_mod.add_entry("hello world", None, "text")
    assert eid > 0
    recent = _storage_mod.get_recent()
    assert len(recent) == 1
    assert recent[0].content == "hello world"


def test_dedup_text():
    """Adding the same text twice results in one row."""
    _storage_mod.add_entry("same text", None, "text")
    _storage_mod.add_entry("same text", None, "text")
    assert len(_storage_mod.get_recent()) == 1


def test_different_texts_not_deduped():
    _storage_mod.add_entry("text A", None, "text")
    _storage_mod.add_entry("text B", None, "text")
    assert len(_storage_mod.get_recent()) == 2


def test_add_image_entry():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    eid = _storage_mod.add_entry(None, fake_png, "image", max_image_size_mb=8)
    assert eid > 0
    recent = _storage_mod.get_recent()
    assert recent[0].type == "image"
    assert recent[0].image_path is not None


def test_image_too_large_rejected():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (9 * 1024 * 1024)
    eid = _storage_mod.add_entry(None, big, "image", max_image_size_mb=8)
    assert eid == -1
    assert _storage_mod.get_recent() == []


def test_pin_unpin():
    _storage_mod.add_entry("pinnable", None, "text")
    entry = _storage_mod.get_recent()[0]
    _storage_mod.pin_entry(entry.id)
    assert _storage_mod.get_recent() == []
    assert len(_storage_mod.get_pinned()) == 1

    _storage_mod.unpin_entry(entry.id)
    assert len(_storage_mod.get_recent()) == 1
    assert _storage_mod.get_pinned() == []


def test_delete_entry():
    _storage_mod.add_entry("to delete", None, "text")
    entry = _storage_mod.get_recent()[0]
    _storage_mod.delete_entry(entry.id)
    assert _storage_mod.get_recent() == []


def test_delete_image_removes_files(tmp_path):
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    eid = _storage_mod.add_entry(None, fake_png, "image")
    entry = _storage_mod.get_recent()[0]
    full = Path(entry.image_path)
    assert full.exists()
    _storage_mod.delete_entry(entry.id)
    assert not full.exists()


def test_clear_history_keeps_pinned():
    _storage_mod.add_entry("keep pinned", None, "text")
    pinned_id = _storage_mod.get_recent()[0].id
    _storage_mod.pin_entry(pinned_id)

    _storage_mod.add_entry("unpinned 1", None, "text")
    _storage_mod.add_entry("unpinned 2", None, "text")

    _storage_mod.clear_history(keep_pinned=True)
    assert _storage_mod.get_recent() == []
    assert len(_storage_mod.get_pinned()) == 1


def test_search():
    _storage_mod.add_entry("hello world", None, "text")
    _storage_mod.add_entry("foobar baz", None, "text")
    results = _storage_mod.search("hello")
    assert len(results) == 1
    assert results[0].content == "hello world"


def test_search_case_insensitive():
    _storage_mod.add_entry("Hello World", None, "text")
    assert len(_storage_mod.search("hello")) == 1
    assert len(_storage_mod.search("WORLD")) == 1


def test_set_tag():
    _storage_mod.add_entry("tagged item", None, "text")
    entry = _storage_mod.get_recent()[0]
    _storage_mod.set_tag(entry.id, "important")
    results = _storage_mod.search("important")
    assert len(results) == 1


def test_trim_history():
    """Seeding 60 items with cap=50 leaves exactly 50, oldest removed."""
    for i in range(60):
        _storage_mod.add_entry(f"item {i}", None, "text", history_limit=1000)
    # Now manually trim
    _storage_mod.trim_history(50)
    recent = _storage_mod.get_recent(100)
    assert len(recent) == 50
    # Most recent 50 should remain — item 59 should be present
    contents = {e.content for e in recent}
    assert "item 59" in contents
    assert "item 0" not in contents


def test_trim_respects_pinned():
    """Pinned items are never removed by trim."""
    _storage_mod.add_entry("pinned item", None, "text")
    entry = _storage_mod.get_recent()[0]
    _storage_mod.pin_entry(entry.id)

    for i in range(55):
        _storage_mod.add_entry(f"recent {i}", None, "text", history_limit=1000)
    _storage_mod.trim_history(50)

    assert len(_storage_mod.get_pinned()) == 1
    assert len(_storage_mod.get_recent(100)) == 50


def test_update_content():
    _storage_mod.add_entry("original text", None, "text")
    entry = _storage_mod.get_recent()[0]
    _storage_mod.update_content(entry.id, "updated text")
    updated = _storage_mod.get_recent()[0]
    assert updated.content == "updated text"
    assert updated.id == entry.id
