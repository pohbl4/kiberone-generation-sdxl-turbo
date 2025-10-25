from __future__ import annotations

import secrets
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi import status as http_status

from ..config import get_settings
from ..sessions import SessionData, session_store
from ..utils.images import normalize_base_image
from .auth import get_session

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_base_image(
    file: UploadFile = File(...),
    session: SessionData = Depends(get_session),
):
    settings = get_settings()
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"error": {"code": "INVALID_TYPE", "message": "Поддерживаются только JPG и PNG"}})

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"error": {"code": "FILE_TOO_LARGE", "message": "Слишком большой файл"}})

    image = normalize_base_image(data)
    image_id = f"img_{secrets.token_hex(8)}"
    session_dir = settings.tmp_dir / session.sid
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / f"{image_id}.png"
    image.save(output_path)
    session_store.register_base_image(session, image_id, output_path)

    return {"image_id": image_id, "width": 512, "height": 512, "url": f"/api/image/{image_id}"}
