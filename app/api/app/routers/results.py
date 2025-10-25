from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from fastapi.responses import FileResponse, JSONResponse

from ..sessions import ResultMeta, SessionData, session_store
from .auth import get_session

router = APIRouter(tags=["results"])


def _error_response(status_code: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _format_filename(meta: ResultMeta) -> str:
    timestamp = meta.created_at.strftime("%Y%m%d-%H%M%S")
    return f"kiberone-gen-{timestamp}.png"


@router.get("/result/{name}")
async def download_result(
    name: str,
    t: str | None = Query(None),
    session: SessionData = Depends(get_session),
):
    meta: ResultMeta | None = None
    if t:
        try:
            meta = session_store.consume_download_token(session, t)
        except ValueError:
            return _error_response(
                http_status.HTTP_401_UNAUTHORIZED,
                code="INVALID_TOKEN",
                message="Invalid token",
            )
        if meta.path.name != name:
            return _error_response(
                http_status.HTTP_404_NOT_FOUND,
                code="RESULT_NOT_FOUND",
                message="Result not found",
            )
    else:
        meta = next((item for item in session.results.values() if item.path.name == name), None)
        if meta is None:
            return _error_response(
                http_status.HTTP_404_NOT_FOUND,
                code="RESULT_NOT_FOUND",
                message="Result not found",
            )

    return FileResponse(
        meta.path,
        media_type="image/png",
        filename=_format_filename(meta),
    )
