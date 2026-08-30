"""Anki .apkg import: stash a parsed package, then commit it into a deck of Word cards."""

from __future__ import annotations

import json
import os
import re
import time
from uuid import uuid4

from fastapi import HTTPException
from fsrs import Card, State
from sqlmodel import Session, select

from app import media_store
from app.anki_import import AnkiPackage, read_media_bytes
from app.models import FsrsCard, MediaFile, Word
from app.schemas import AnkiCommitResponse
from app.services import decks as deck_svc
from app.services import fsrs as fsrs_svc
from app.time_utils import utcnow

_STORE: dict[str, tuple[float, AnkiPackage]] = {}
_TTL_SECONDS = 30 * 60


def _gc() -> None:
    cutoff = time.time() - _TTL_SECONDS
    for k in [k for k, (ts, _) in _STORE.items() if ts < cutoff]:
        _STORE.pop(k, None)


def stash(pkg: AnkiPackage) -> str:
    _gc()
    import_id = uuid4().hex
    _STORE[import_id] = (time.time(), pkg)
    return import_id


def fetch(import_id: str) -> AnkiPackage:
    _gc()
    entry = _STORE.get(import_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Import expired or not found — please re-upload")
    return entry[1]


def discard(import_id: str) -> None:
    _STORE.pop(import_id, None)


# ---- FSRS state approximation from Anki scheduling ----

_ANKI_STATE = {1: State.Learning, 2: State.Review, 3: State.Relearning}


def utcnow_aware():
    from datetime import timezone

    return utcnow().replace(tzinfo=timezone.utc)


def _anki_due_datetime(sched, crt: int):
    """Anki's `due` -> a real datetime (aware UTC).

    Review cards: `due` is days since the collection's creation (`col.crt`).
    Learning/relearning: `due` is a unix timestamp (seconds).
    """
    from datetime import datetime, timedelta, timezone

    now = utcnow_aware()
    if not crt:
        return now
    if sched.type == 2:
        return datetime.fromtimestamp(crt, tz=timezone.utc) + timedelta(days=sched.due)
    if sched.type in (1, 3):
        if sched.due > 10**9:  # looks like a timestamp
            return datetime.fromtimestamp(sched.due, tz=timezone.utc)
        return datetime.fromtimestamp(crt, tz=timezone.utc) + timedelta(days=sched.due)
    return now


def _fsrs_fields(sched, *, crt: int = 0, import_progress: bool) -> dict:
    if not import_progress or sched is None or sched.type == 0 or sched.ivl <= 0:
        fields = fsrs_svc.new_card()
        if sched is not None:
            fields["reps"] = sched.reps
            fields["lapses"] = sched.lapses
        return fields

    from datetime import timedelta

    ivl_days = float(sched.ivl)
    stability = max(ivl_days, 0.5)
    # Anki ease 2500 (default) -> difficulty ~5; 1300 -> ~9; 3100 -> ~3
    difficulty = min(10.0, max(1.0, 11.7 - sched.factor / 370.0))

    due = _anki_due_datetime(sched, crt)
    # if the card was overdue in Anki it stays overdue here (immediately due)
    last_review = min(utcnow_aware(), due - timedelta(days=ivl_days))

    card = Card(
        state=_ANKI_STATE.get(sched.type, State.Review),
        step=0,
        stability=stability,
        difficulty=difficulty,
        due=due,
        last_review=last_review,
    )
    fields = fsrs_svc.card_fields(card)
    fields["reps"] = sched.reps
    fields["lapses"] = sched.lapses
    return fields


# ---- commit ----


_SEPARATORS = re.compile(r"\s*[–—:,;/|]\s*|\s+[-]\s+|\t|\n")


def _first_line(text: str) -> str:
    return text.split("\n", 1)[0].strip() if text else ""


def _extract_word(raw: str, mode: str) -> str:
    text = _first_line(raw)
    if mode == "before_separator":
        text = _SEPARATORS.split(text, maxsplit=1)[0]
    return text.strip()


def _attach_audio(
    session: Session,
    word_id: int,
    note,
    pkg: AnkiPackage,
    field_kinds: dict[str | None, str],
    *,
    replace: bool,
) -> None:
    if not pkg.raw or not note.audio:
        return
    if replace:
        for m in session.exec(
            select(MediaFile).where(
                MediaFile.word_id == word_id, MediaFile.source == "anki_import"
            )
        ).all():
            media_store.remove(m.filename)
            session.delete(m)

    seen: set[str] = set()
    for field, kind in field_kinds.items():
        if not field:
            continue
        for anki_name in note.audio.get(field, []):
            if anki_name in seen:
                continue
            seen.add(anki_name)
            member = pkg.media_map.get(anki_name)
            if not member:
                continue
            try:
                data = read_media_bytes(pkg.raw, member)
            except Exception:
                continue
            ext = os.path.splitext(anki_name)[1] or ".mp3"
            stored = media_store.save(data, ext)
            session.add(
                MediaFile(
                    word_id=word_id,
                    kind=kind,
                    filename=stored,
                    mime=media_store.guess_mime(anki_name, "audio/mpeg"),
                    source="anki_import",
                )
            )


def commit(
    session: Session,
    *,
    import_id: str,
    deck_name: str,
    language: str,
    note_type: str,
    word_field: str,
    word_extract: str = "whole",
    prompt_field: str | None = None,
    meaning_field: str | None = None,
    examples_field: str | None = None,
    import_progress: bool = True,
    on_duplicate: str = "skip",
) -> AnkiCommitResponse:
    pkg = fetch(import_id)

    fields = pkg.note_types.get(note_type)
    if fields is None:
        raise HTTPException(status_code=400, detail=f"Note type '{note_type}' not in this package")
    for label, f in (("word_field", word_field), ("prompt_field", prompt_field),
                     ("meaning_field", meaning_field), ("examples_field", examples_field)):
        if f is not None and f not in fields:
            raise HTTPException(status_code=400, detail=f"{label} '{f}' not in note type '{note_type}'")

    deck_name = deck_name.strip()
    existing_deck = session.exec(
        select(deck_svc.Deck).where(deck_svc.Deck.name == deck_name)
    ).first()
    deck = existing_deck or deck_svc.create_deck(session, name=deck_name, language=language)

    imported = updated = skipped = 0
    for note in pkg.notes_for(note_type):
        word = _extract_word(note.fields.get(word_field, ""), word_extract)
        if not word:
            skipped += 1
            continue

        prompt = (note.fields.get(prompt_field, "").strip() or None) if prompt_field else None
        meaning = (note.fields.get(meaning_field, "") if meaning_field else "").strip()
        definitions = json.dumps(
            [line.strip() for line in meaning.split("\n") if line.strip()], ensure_ascii=False
        )
        examples = "[]"
        if examples_field:
            examples = json.dumps(
                [
                    line.strip()
                    for line in note.fields.get(examples_field, "").split("\n")
                    if line.strip()
                ],
                ensure_ascii=False,
            )
        fsrs_fields = _fsrs_fields(note.sched, crt=pkg.crt, import_progress=import_progress)
        field_kinds = {
            word_field: "word",
            examples_field: "example",
            meaning_field: "extra",
            prompt_field: "extra",
        }

        existing = session.exec(
            select(Word).where(Word.word == word, Word.language == language)
        ).first()

        if existing is not None:
            if on_duplicate != "overwrite":
                skipped += 1
                continue
            w = existing
            w.deck_id = deck.id
            w.prompt = prompt
            w.translation = _first_line(meaning) or None
            w.definitions = definitions
            w.examples = examples
            w.source = "anki_import"
            w.updated_at = utcnow()
            fc = session.exec(select(FsrsCard).where(FsrsCard.word_id == w.id)).first()
            if fc is not None:
                for k, v in fsrs_fields.items():
                    setattr(fc, k, v)
                session.add(fc)
            session.add(w)
            _attach_audio(session, w.id, note, pkg, field_kinds, replace=True)
            updated += 1
            continue

        w = Word(
            word=word,
            language=language,
            deck_id=deck.id,
            prompt=prompt,
            source="anki_import",
            translation=_first_line(meaning) or None,
            definitions=definitions,
            examples=examples,
            collocations="[]",
        )
        session.add(w)
        session.flush()
        session.add(FsrsCard(word_id=w.id, **fsrs_fields))
        _attach_audio(session, w.id, note, pkg, field_kinds, replace=False)
        imported += 1

    session.commit()
    discard(import_id)
    return AnkiCommitResponse(
        deck_id=deck.id,
        deck_name=deck.name,
        imported=imported,
        updated=updated,
        skipped=skipped,
    )
