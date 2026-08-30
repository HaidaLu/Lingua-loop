"""Files on disk for MediaFile rows — under settings.media_dir."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from app.config import settings


def _dir() -> Path:
    p = Path(settings.media_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(data: bytes, ext: str) -> str:
    ext = ext if ext.startswith(".") else "." + ext
    name = uuid.uuid4().hex + ext
    (_dir() / name).write_bytes(data)
    return name


def full_path(filename: str) -> Path:
    return _dir() / filename


def remove(filename: str) -> None:
    try:
        (_dir() / filename).unlink()
    except FileNotFoundError:
        pass


def guess_mime(filename: str, default: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(filename)[0] or default
