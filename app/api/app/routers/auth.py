from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import get_settings
from ..sessions import SessionData, session_store

router = APIRouter(prefix="/auth", tags=["auth"])


COOKIE_NAME = "sid"


class LoginRequest(BaseModel):
    password: str


def get_session(request: Request) -> SessionData:
    sid = request.cookies.get(COOKIE_NAME)
    return session_store.get_session(sid)


def _set_session_cookie(response: Response, session: SessionData) -> None:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_min)
    response.set_cookie(
        COOKIE_NAME,
        session.sid,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        expires=expires,
        max_age=settings.session_ttl_min * 60,
    )


def _build_user_info(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    host = (forwarded.split(",")[0].strip() if forwarded else None) or (request.client.host if request.client else None)
    user_agent = request.headers.get("user-agent")
    parts = []
    if host:
        parts.append(host)
    if user_agent:
        parts.append(user_agent[:120])
    return " | ".join(parts) if parts else "unknown"


@router.post("/login")
async def login(payload: LoginRequest, response: Response, request: Request):
    settings = get_settings()
    if payload.password != settings.auth_pass:
        return JSONResponse(
            {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid password"}},
            status_code=http_status.HTTP_401_UNAUTHORIZED,
        )

    session = session_store.create_session(user_info=_build_user_info(request))
    _set_session_cookie(response, session)
    return {"ok": True, "user_id": session.user_id}


@router.post("/logout")
async def logout(request: Request):
    sid = request.cookies.get(COOKIE_NAME)
    if sid:
        session_store.remove_session(sid)
    response = Response(status_code=http_status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/me")
async def me(session: SessionData = Depends(get_session)):
    return {"ok": True, "sid": session.sid, "user_id": session.user_id, "user_info": session.user_info}


@router.post("/refresh")
async def refresh_session(response: Response, session: SessionData = Depends(get_session)):
    _set_session_cookie(response, session)
    return {"ok": True}
