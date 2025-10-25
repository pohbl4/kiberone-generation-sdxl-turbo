from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..sessions import SessionData, session_store
from ..utils.templates import (
    TEMPLATE_DEFINITIONS,
    decode_template_image,
    render_template_placeholder,
)
from .auth import get_session

router = APIRouter(tags=["canvas"])


class TemplateSelection(BaseModel):
    template_id: str = Field(..., alias="template_id")
    image_data: str | None = Field(default=None, alias="image_data")

    class Config:
        populate_by_name = True


@router.post("/canvas/apply-result")
async def apply_result(payload: dict[str, str], session: SessionData = Depends(get_session)):
    result_url = payload.get("result_url")
    if not result_url:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="result_url is required")

    filename = result_url.split("/")[-1]
    result = next((meta for meta in session.results.values() if meta.path.name == filename), None)
    if not result:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Result not found")

    settings = get_settings()
    session_dir = settings.tmp_dir / session.sid
    session_dir.mkdir(parents=True, exist_ok=True)
    image_id = f"img_{secrets.token_hex(8)}"
    new_path = session_dir / f"{image_id}.png"
    new_path.write_bytes(result.path.read_bytes())
    session_store.register_base_image(session, image_id, new_path)

    return {"image_id": image_id, "url": f"/api/image/{image_id}"}


@router.post("/canvas/select-template")
async def select_template(selection: TemplateSelection, session: SessionData = Depends(get_session)):
    template_id = selection.template_id
    if template_id not in TEMPLATE_DEFINITIONS:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Unknown template")

    if selection.image_data:
        try:
            image = decode_template_image(selection.image_data)
        except ValueError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid template payload",
            ) from exc
    else:
        try:
            image = render_template_placeholder(template_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Template asset unavailable",
            ) from exc

    try:
        image = image.convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Failed to prepare template",
        ) from exc
    settings = get_settings()
    session_dir = settings.tmp_dir / session.sid
    session_dir.mkdir(parents=True, exist_ok=True)
    image_id = f"img_{secrets.token_hex(8)}"
    output_path = session_dir / f"{image_id}.png"
    image.save(output_path)
    session_store.register_base_image(session, image_id, output_path)

    return {"image_id": image_id, "url": f"/api/image/{image_id}"}
