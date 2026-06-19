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
