from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.services import media as media_svc

router = APIRouter(
    prefix="/api/media", tags=["media"], dependencies=[Depends(get_current_user)]
)


@router.get("/{media_id}")
def get_media(media_id: int, session: Session = Depends(get_session)):
    path, mime = media_svc.file_for(session, media_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="media file missing on disk")
    return FileResponse(path, media_type=mime)


@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: int, session: Session = Depends(get_session)):
    media_svc.delete(session, media_id)
    return Response(status_code=204)
