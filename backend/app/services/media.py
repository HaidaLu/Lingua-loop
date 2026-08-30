from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app import media_store
from app.models import MediaFile, Word
from app.schemas import MediaOut

_REC_EXT = {"webm": ".webm", "ogg": ".ogg", "opus": ".ogg", "mp4": ".m4a", "m4a": ".m4a", "mpeg": ".mp3", "wav": ".wav"}
_MIME_KIND = (("image/", "image"), ("audio/", "audio"), ("video/", "video"))


def _out(m: MediaFile) -> MediaOut:
    return MediaOut(id=m.id, kind=m.kind, mime=m.mime, source=m.source)


def list_for_word(session: Session, word_id: int) -> list[MediaOut]:
    rows = session.exec(
        select(MediaFile).where(MediaFile.word_id == word_id).order_by(MediaFile.id)
    ).all()
    return [_out(m) for m in rows]


def by_words(session: Session, word_ids: list[int]) -> dict[int, list[MediaOut]]:
    if not word_ids:
        return {}
    rows = session.exec(
        select(MediaFile).where(MediaFile.word_id.in_(word_ids)).order_by(MediaFile.id)
    ).all()
    out: dict[int, list[MediaOut]] = {}
    for m in rows:
        out.setdefault(m.word_id, []).append(_out(m))
    return out


def add_recording(session: Session, word_id: int, data: bytes, mime: str) -> MediaOut:
    if session.get(Word, word_id) is None:
        raise HTTPException(status_code=404, detail="word not found")
    ext = next((v for k, v in _REC_EXT.items() if k in (mime or "").lower()), ".webm")
    stored = media_store.save(data, ext)
    m = MediaFile(
        word_id=word_id, kind="user_recording", filename=stored,
        mime=mime or "audio/webm", source="recording",
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return _out(m)


def add_attachment(
    session: Session, word_id: int, data: bytes, mime: str, filename: str | None
) -> MediaOut:
    if session.get(Word, word_id) is None:
        raise HTTPException(status_code=404, detail="word not found")
    mime = (mime or "").lower()
    kind = next((k for pfx, k in _MIME_KIND if mime.startswith(pfx)), None)
    if kind is None:
        raise HTTPException(status_code=400, detail="only image / audio / video files are supported")
    ext = (
        os.path.splitext(filename or "")[1]
        or mimetypes.guess_extension(mime)
        or ".bin"
    )
    stored = media_store.save(data, ext)
    m = MediaFile(word_id=word_id, kind=kind, filename=stored, mime=mime, source="upload")
    session.add(m)
    session.commit()
    session.refresh(m)
    return _out(m)


def file_for(session: Session, media_id: int) -> tuple[Path, str]:
    m = session.get(MediaFile, media_id)
    if m is None:
        raise HTTPException(status_code=404, detail="media not found")
    return media_store.full_path(m.filename), m.mime


def delete(session: Session, media_id: int) -> None:
    m = session.get(MediaFile, media_id)
    if m is None:
        raise HTTPException(status_code=404, detail="media not found")
    media_store.remove(m.filename)
    session.delete(m)
    session.commit()


def delete_for_word(session: Session, word_id: int) -> None:
    for m in session.exec(select(MediaFile).where(MediaFile.word_id == word_id)).all():
        media_store.remove(m.filename)
        session.delete(m)
