from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi import status as http_status

from ..sessions import SessionData
from .auth import get_session

router = APIRouter(tags=["images"])


@router.get("/image/{image_id}")
async def get_image(image_id: str, session: SessionData = Depends(get_session)):
    path = session.base_images.get(image_id)
    if not path:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Image not found")
    return FileResponse(path)
