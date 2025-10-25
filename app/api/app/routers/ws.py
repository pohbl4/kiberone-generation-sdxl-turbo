from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..jobs import job_manager
from ..sessions import session_store
from .auth import COOKIE_NAME

router = APIRouter()


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    sid_hint = websocket.cookies.get(COOKIE_NAME) or websocket.query_params.get("sid")
    session = session_store.try_get_session(sid_hint)

    def resolve_session(candidate: str | None):
        nonlocal session, sid_hint
        resolved = session_store.try_get_session(candidate)
        if resolved:
            session = resolved
            sid_hint = resolved.sid
        return resolved

    try:
        while True:
            message = await websocket.receive_json()
            if message.get("action") != "subscribe":
                continue

            job_id = message.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                continue

            candidate_sid = message.get("sid") if isinstance(message.get("sid"), str) else None
            resolved = session or resolve_session(candidate_sid) or resolve_session(sid_hint)
            if not resolved:
                await websocket.send_json(
                    {"type": "error", "job_id": job_id, "message": "Unauthorized"}
                )
                continue

            try:
                job = job_manager.get_job(job_id)
            except KeyError:
                await websocket.send_json(
                    {"type": "error", "job_id": job_id, "message": "Job not found"}
                )
                continue

            if job.session.sid != resolved.sid:
                await websocket.send_json(
                    {"type": "error", "job_id": job_id, "message": "Unauthorized"}
                )
                continue

            await job_manager.subscribe(job_id, websocket)
    except WebSocketDisconnect:
        return


router.add_api_websocket_route("/ws", websocket_endpoint)
router.add_api_websocket_route("/ws/", websocket_endpoint)
