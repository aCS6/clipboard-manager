"""SQLite-backed storage layer. The only module that touches history.db or images/."""
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from clipboard_manager.models import ClipEntry
from clipboard_manager.utils.hashing import sha256_bytes, sha256_text
from clipboard_manager.utils.logger import get_logger

log = get_logger(__name__)

_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "clipboard-manager"
_IMAGES_DIR = _DATA_DIR / "images"
_DB_PATH = _DATA_DIR / "history.db"

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        raise RuntimeError("storage not initialised; call init_db() first")
    return _conn


def init_db(db_path: str | None = None) -> None:
    global _conn
    path = Path(db_path) if db_path else _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(path), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS clip_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL CHECK(type IN ('text','image')),
            content     TEXT,
            image_path  TEXT,
            thumb_path  TEXT,
            created_at  TEXT NOT NULL,
            pinned      INTEGER NOT NULL DEFAULT 0,
            tag         TEXT,
            hash        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hash    ON clip_items(hash);
        CREATE INDEX IF NOT EXISTS idx_pinned  ON clip_items(pinned);
        CREATE INDEX IF NOT EXISTS idx_created ON clip_items(created_at);
    """)
    _conn.commit()


def _row_to_entry(row: sqlite3.Row) -> ClipEntry:
    return ClipEntry(
        id=row["id"],
        type=row["type"],
        content=row["content"],
        image_path=row["image_path"],
        thumb_path=row["thumb_path"],
        created_at=datetime.fromisoformat(row["created_at"]),
        pinned=bool(row["pinned"]),
        tag=row["tag"],
        hash=row["hash"],
    )


def add_entry(
    content: Optional[str],
    image_bytes: Optional[bytes],
    content_type: str,
    max_image_size_mb: int = 8,
    history_limit: int = 50,
) -> int:
    """Returns new row id, or existing row id if duplicate of most recent entry."""
    conn = _get_conn()

    if content_type == "text":
        if not content:
            return -1
        h = sha256_text(content)
    else:
        if not image_bytes:
            return -1
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > max_image_size_mb:
            log.info("Image %.1fMB exceeds limit %dMB, skipping", size_mb, max_image_size_mb)
            return -1
        h = sha256_bytes(image_bytes)

    # De-dup against the single most recent entry
    row = conn.execute(
        "SELECT id, hash FROM clip_items ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row and row["hash"] == h:
        return row["id"]

    image_path = thumb_path = None
    if content_type == "image":
        image_path, thumb_path = _save_image(image_bytes)

    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO clip_items (type, content, image_path, thumb_path, created_at, hash)"
        " VALUES (?,?,?,?,?,?)",
        (content_type, content, str(image_path) if image_path else None,
         str(thumb_path) if thumb_path else None, now, h),
    )
    conn.commit()
    entry_id = cur.lastrowid
    trim_history(history_limit)
    return entry_id


def _save_image(image_bytes: bytes) -> tuple[Path, Path]:
    """Write full PNG and a 128px thumbnail, return (full_path, thumb_path)."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib

    uid = uuid.uuid4().hex
    full_path = _IMAGES_DIR / f"{uid}.png"
    thumb_path = _IMAGES_DIR / f"{uid}_thumb.png"

    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.write(image_bytes)
    loader.close()
    pixbuf = loader.get_pixbuf()
    pixbuf.savev(str(full_path), "png", [], [])

    # thumbnail — scale to fit within 128px
    w, h = pixbuf.get_width(), pixbuf.get_height()
    scale = 128 / max(w, h)
    thumb = pixbuf.scale_simple(int(w * scale), int(h * scale), GdkPixbuf.InterpType.BILINEAR)
    thumb.savev(str(thumb_path), "png", [], [])

    return full_path, thumb_path


def get_recent(limit: int = 50) -> list[ClipEntry]:
    rows = _get_conn().execute(
        "SELECT * FROM clip_items WHERE pinned=0 ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_pinned() -> list[ClipEntry]:
    rows = _get_conn().execute(
        "SELECT * FROM clip_items WHERE pinned=1 ORDER BY id DESC"
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def pin_entry(entry_id: int) -> None:
    _get_conn().execute("UPDATE clip_items SET pinned=1 WHERE id=?", (entry_id,))
    _get_conn().commit()


def unpin_entry(entry_id: int) -> None:
    _get_conn().execute("UPDATE clip_items SET pinned=0 WHERE id=?", (entry_id,))
    _get_conn().commit()


def delete_entry(entry_id: int) -> None:
    conn = _get_conn()
    row = conn.execute("SELECT image_path, thumb_path FROM clip_items WHERE id=?", (entry_id,)).fetchone()
    if row:
        for p in (row["image_path"], row["thumb_path"]):
            if p and Path(p).exists():
                Path(p).unlink(missing_ok=True)
    conn.execute("DELETE FROM clip_items WHERE id=?", (entry_id,))
    conn.commit()


def clear_history(keep_pinned: bool = True) -> None:
    conn = _get_conn()
    if keep_pinned:
        rows = conn.execute("SELECT image_path, thumb_path FROM clip_items WHERE pinned=0").fetchall()
    else:
        rows = conn.execute("SELECT image_path, thumb_path FROM clip_items").fetchall()
    for row in rows:
        for p in (row["image_path"], row["thumb_path"]):
            if p and Path(p).exists():
                Path(p).unlink(missing_ok=True)
    if keep_pinned:
        conn.execute("DELETE FROM clip_items WHERE pinned=0")
    else:
        conn.execute("DELETE FROM clip_items")
    conn.commit()


def search(query: str) -> list[ClipEntry]:
    q = f"%{query}%"
    rows = _get_conn().execute(
        "SELECT * FROM clip_items WHERE (content LIKE ? OR tag LIKE ?) ORDER BY id DESC",
        (q, q),
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def set_tag(entry_id: int, tag: Optional[str]) -> None:
    _get_conn().execute("UPDATE clip_items SET tag=? WHERE id=?", (tag, entry_id))
    _get_conn().commit()


def update_content(entry_id: int, new_content: str) -> None:
    from clipboard_manager.utils.hashing import sha256_text
    h = sha256_text(new_content)
    _get_conn().execute(
        "UPDATE clip_items SET content=?, hash=? WHERE id=?", (new_content, h, entry_id)
    )
    _get_conn().commit()


def trim_history(max_unpinned: int) -> None:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, image_path, thumb_path FROM clip_items WHERE pinned=0 ORDER BY id DESC"
    ).fetchall()
    excess = rows[max_unpinned:]
    for row in excess:
        for p in (row["image_path"], row["thumb_path"]):
            if p and Path(p).exists():
                Path(p).unlink(missing_ok=True)
        conn.execute("DELETE FROM clip_items WHERE id=?", (row["id"],))
    if excess:
        conn.commit()
