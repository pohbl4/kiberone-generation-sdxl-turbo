from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..sessions import SessionData, session_store
from .auth import get_session

router = APIRouter(tags=["history"])


@router.post("/history/undo")
async def history_undo(session: SessionData = Depends(get_session)):
    try:
        result = session_store.pop_history(session)
    except HTTPException as exc:
        raise exc
    return {
        "result_id": result.result_id,
        "result_url": f"/api/result/{result.path.name}",
        "seed": result.seed,
        "quality": result.quality_effective,
    }
