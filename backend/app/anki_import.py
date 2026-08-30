"""Parse an Anki .apkg / .colpkg package into plain Python structures.

An .apkg is a ZIP holding a SQLite collection file (collection.anki2 / .anki21, or
zstd-compressed .anki21b) plus media. We only read notes + card scheduling.
"""

from __future__ import annotations

import html
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

FIELD_SEP = "\x1f"
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


@dataclass
class AnkiCardSched:
    type: int  # 0 new, 1 learning, 2 review, 3 relearning
    ivl: int  # interval; positive = days, negative = seconds (learning)
    factor: int  # ease factor x1000 (2500 = default)
    reps: int
    lapses: int
    due: int


@dataclass
class AnkiNote:
    note_type: str
    fields: dict[str, str]  # field name -> cleaned plain text
    audio: dict[str, list[str]]  # field name -> [sound:] filenames referenced in that field
    sched: AnkiCardSched | None  # best (most-progressed) card for this note


@dataclass
class AnkiPackage:
    note_types: dict[str, list[str]]  # note type name -> ordered field names
    notes: list[AnkiNote]
    anki_decks: list[str]
    crt: int = 0  # collection creation epoch (seconds); review `due` is days since this
    media_map: dict[str, str] = field(default_factory=dict)  # anki filename -> zip member name
    raw: bytes = field(default=b"", repr=False)  # the original .apkg bytes, for media extraction

    def notes_for(self, note_type: str) -> list[AnkiNote]:
        return [n for n in self.notes if n.note_type == note_type]


# ---- HTML / markup cleaning ----

_CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}", re.S)
_SOUND = re.compile(r"\[sound:[^\]]*\]")
_SOUND_REF = re.compile(r"\[sound:([^\]]+)\]")
_BR = re.compile(r"<br\s*/?>", re.I)
_BLOCK_END = re.compile(r"</(div|p|li|tr|h[1-6])>", re.I)
_TAG = re.compile(r"<[^>]+>")
_INLINE_WS = re.compile(r"[ \t ]+")
_MULTI_NL = re.compile(r"\n\s*\n+")


def clean_html(s: str) -> str:
    if not s:
        return ""
    s = _CLOZE.sub(r"\1", s)
    s = _SOUND.sub("", s)
    s = _BR.sub("\n", s)
    s = _BLOCK_END.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = _INLINE_WS.sub(" ", s)
    s = _MULTI_NL.sub("\n", s)
    return s.strip()


# ---- collection + media extraction ----


def _zstd_decompress(raw: bytes) -> bytes:
    import zstandard

    return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)).read()


def _read_collection_bytes(zf: zipfile.ZipFile) -> bytes:
    names = set(zf.namelist())
    if "collection.anki21b" in names:
        return _zstd_decompress(zf.read("collection.anki21b"))
    for n in ("collection.anki21", "collection.anki2"):
        if n in names:
            return zf.read(n)
    raise ValueError("no collection file found inside the package")


def _read_varint(b: bytes, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = b[i]
        i += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, i
        shift += 7


def _pb_skip(b: bytes, i: int, wire: int) -> int:
    if wire == 0:
        _, i = _read_varint(b, i)
    elif wire == 2:
        n, i = _read_varint(b, i)
        i += n
    elif wire == 5:
        i += 4
    elif wire == 1:
        i += 8
    return i


def _pb_first_string(entry: bytes) -> str:
    i = 0
    while i < len(entry):
        tag, i = _read_varint(entry, i)
        if (tag >> 3) == 1 and (tag & 7) == 2:
            n, i = _read_varint(entry, i)
            return entry[i : i + n].decode("utf-8", "replace")
        i = _pb_skip(entry, i, tag & 7)
    return ""


def _parse_media_entries_pb(blob: bytes) -> list[str]:
    """MediaEntries protobuf -> ordered list of file names (entry i -> zip member str(i))."""
    names: list[str] = []
    i = 0
    while i < len(blob):
        tag, i = _read_varint(blob, i)
        if (tag >> 3) == 1 and (tag & 7) == 2:
            n, i = _read_varint(blob, i)
            names.append(_pb_first_string(blob[i : i + n]))
            i += n
        else:
            i = _pb_skip(blob, i, tag & 7)
    return names


def _media_manifest(zf: zipfile.ZipFile) -> dict[str, str]:
    """{ anki filename : zip member name }, for both the legacy JSON and the v3 protobuf format."""
    if "media" not in zf.namelist():
        return {}
    raw = zf.read("media")
    if raw[:4] == _ZSTD_MAGIC:  # v3: zstd(protobuf MediaEntries)
        try:
            names = _parse_media_entries_pb(_zstd_decompress(raw))
        except Exception:
            return {}
        return {name: str(i) for i, name in enumerate(names) if name}
    try:  # v1/v2: JSON { "0": "filename.mp3" }
        return {v: k for k, v in json.loads(raw.decode("utf-8")).items()}
    except Exception:
        return {}


def read_media_bytes(raw_apkg: bytes, member: str) -> bytes:
    """Read one media file out of the .apkg by its zip member name, decompressing if needed."""
    zf = zipfile.ZipFile(io.BytesIO(raw_apkg))
    data = zf.read(member)
    return _zstd_decompress(data) if data[:4] == _ZSTD_MAGIC else data


def _read_note_types(con: sqlite3.Connection) -> dict[int, dict]:
    """mid -> {'name': str, 'fields': [field names in order]}."""
    out: dict[int, dict] = {}
    row = con.execute("SELECT models FROM col").fetchone()
    models_json = row["models"] if row else None
    if models_json and models_json not in ("", "{}"):
        for mid, m in json.loads(models_json).items():
            flds = [f["name"] for f in sorted(m["flds"], key=lambda x: x["ord"])]
            out[int(mid)] = {"name": m["name"], "fields": flds}
        return out
    # newer schema (v18+): notetypes + fields tables
    try:
        for nt in con.execute("SELECT id, name FROM notetypes"):
            flds = [
                r["name"]
                for r in con.execute(
                    "SELECT name FROM fields WHERE ntid = ? ORDER BY ord", (nt["id"],)
                )
            ]
            out[nt["id"]] = {"name": nt["name"], "fields": flds}
    except sqlite3.OperationalError:
        pass
    return out


def _read_deck_names(con: sqlite3.Connection) -> list[str]:
    names: list[str] = []
    row = con.execute("SELECT decks FROM col").fetchone()
    decks_json = row["decks"] if row else None
    if decks_json and decks_json not in ("", "{}"):
        for d in json.loads(decks_json).values():
            if d.get("name") and d["name"] != "Default":
                names.append(d["name"])
    else:
        try:
            for r in con.execute("SELECT name FROM decks"):
                if r["name"] and r["name"] != "Default":
                    names.append(r["name"])
        except sqlite3.OperationalError:
            pass
    return sorted(set(names))


def _best_card_per_note(con: sqlite3.Connection) -> dict[int, AnkiCardSched]:
    best: dict[int, AnkiCardSched] = {}
    for c in con.execute("SELECT nid, type, ivl, factor, reps, lapses, due FROM cards"):
        sched = AnkiCardSched(
            type=c["type"] or 0,
            ivl=c["ivl"] or 0,
            factor=c["factor"] or 2500,
            reps=c["reps"] or 0,
            lapses=c["lapses"] or 0,
            due=c["due"] or 0,
        )
        prev = best.get(c["nid"])
        if prev is None or sched.ivl > prev.ivl:
            best[c["nid"]] = sched
    return best


def parse_apkg(data: bytes) -> AnkiPackage:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("not a valid .apkg (bad zip)") from e

    col_bytes = _read_collection_bytes(zf)
    media_map = _media_manifest(zf)
    tmp = tempfile.NamedTemporaryFile(suffix=".anki2", delete=False)
    try:
        tmp.write(col_bytes)
        tmp.close()
        con = sqlite3.connect(tmp.name)
        con.row_factory = sqlite3.Row
        try:
            crt_row = con.execute("SELECT crt FROM col").fetchone()
            crt = int(crt_row["crt"]) if crt_row else 0
            note_types = _read_note_types(con)
            if not note_types:
                raise ValueError("no note types found in the collection")
            deck_names = _read_deck_names(con)
            sched_by_nid = _best_card_per_note(con)

            notes: list[AnkiNote] = []
            for n in con.execute("SELECT id, mid, flds FROM notes"):
                nt = note_types.get(n["mid"])
                if not nt:
                    continue
                values = n["flds"].split(FIELD_SEP)
                field_names = nt["fields"]
                fields: dict[str, str] = {}
                audio: dict[str, list[str]] = {}
                for i, name in enumerate(field_names):
                    raw_val = values[i] if i < len(values) else ""
                    refs = _SOUND_REF.findall(raw_val)
                    if refs:
                        audio[name] = refs
                    fields[name] = clean_html(raw_val)
                notes.append(
                    AnkiNote(nt["name"], fields, audio, sched_by_nid.get(n["id"]))
                )
        finally:
            con.close()
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    used = {n.note_type for n in notes}
    return AnkiPackage(
        note_types={v["name"]: v["fields"] for v in note_types.values() if v["name"] in used},
        notes=notes,
        anki_decks=deck_names,
        crt=crt,
        media_map=media_map,
        raw=data,
    )
