from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.anki_import import parse_apkg
from app.auth import get_current_user
from app.db import get_session
from app.schemas import (
    AnkiCommitRequest,
    AnkiCommitResponse,
    AnkiNoteType,
    AnkiPreviewResponse,
    AnkiSample,
)
from app.services import anki_import

router = APIRouter(
    prefix="/api/import", tags=["import"], dependencies=[Depends(get_current_user)]
)

_MAX_BYTES = 200 * 1024 * 1024
_SAMPLES_PER_TYPE = 4


@router.post("/anki/preview", response_model=AnkiPreviewResponse)
async def anki_preview(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith((".apkg", ".colpkg")):
        raise HTTPException(status_code=400, detail="Please upload an Anki .apkg file")

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (limit 200 MB)")

    try:
        pkg = parse_apkg(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the .apkg: {e}") from e

    if not pkg.notes:
        raise HTTPException(status_code=400, detail="The package contains no notes")

    import_id = anki_import.stash(pkg)

    note_types = [
        AnkiNoteType(name=nt, fields=fields, note_count=len(pkg.notes_for(nt)))
        for nt, fields in pkg.note_types.items()
    ]
    samples: list[AnkiSample] = []
    for nt in pkg.note_types:
        for n in pkg.notes_for(nt)[:_SAMPLES_PER_TYPE]:
            samples.append(AnkiSample(note_type=nt, fields=n.fields))

    with_progress = sum(1 for n in pkg.notes if n.sched and n.sched.type != 0 and n.sched.ivl > 0)
    suggested = pkg.anki_decks[0].split("::")[-1] if pkg.anki_decks else name.rsplit("/", 1)[-1]
    suggested = suggested.removesuffix(".apkg").removesuffix(".colpkg") or "Imported deck"

    return AnkiPreviewResponse(
        import_id=import_id,
        note_types=note_types,
        anki_decks=pkg.anki_decks,
        total_notes=len(pkg.notes),
        notes_with_progress=with_progress,
        samples=samples,
        suggested_deck_name=suggested,
    )


@router.post("/anki/commit", response_model=AnkiCommitResponse)
def anki_commit(req: AnkiCommitRequest, session: Session = Depends(get_session)):
    return anki_import.commit(
        session,
        import_id=req.import_id,
        deck_name=req.deck_name,
        language=req.language,
        note_type=req.note_type,
        word_field=req.word_field,
        word_extract=req.word_extract,
        prompt_field=req.prompt_field,
        meaning_field=req.meaning_field,
        examples_field=req.examples_field,
        import_progress=req.import_progress,
        on_duplicate=req.on_duplicate,
    )
