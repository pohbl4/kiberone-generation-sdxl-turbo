from __future__ import annotations

import secrets
import string
import shutil
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Dict, Optional

from fastapi import HTTPException, status

from .config import get_settings


@dataclass
class ResultMeta:
    result_id: str
    path: Path
    seed: Optional[int]
    quality_requested: str
    quality_effective: str
    created_at: datetime


@dataclass
class SessionData:
    sid: str
    user_id: str
    user_info: str
    created_at: datetime
    last_seen: datetime
    base_images: Dict[str, Path] = field(default_factory=dict)
    current_base: Optional[str] = None
    results: Dict[str, ResultMeta] = field(default_factory=dict)
    history: Deque[str] = field(default_factory=lambda: deque(maxlen=5))
    download_tokens: Dict[str, ResultMeta] = field(default_factory=dict)
    active_jobs: set[str] = field(default_factory=set)

    def touch(self) -> None:
        self.last_seen = datetime.utcnow()


class SessionStore:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._sessions: Dict[str, SessionData] = {}

    def _generate_sid(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return "sid_" + "".join(secrets.choice(alphabet) for _ in range(32))

    def _generate_user_id(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return "user_" + "".join(secrets.choice(alphabet) for _ in range(16))

    def create_session(self, *, user_info: str | None = None) -> SessionData:
        sid = self._generate_sid()
        user_id = self._generate_user_id()
        now = datetime.utcnow()
        session = SessionData(
            sid=sid,
            user_id=user_id,
            user_info=user_info or "unknown",
            created_at=now,
            last_seen=now,
        )
        self._sessions[sid] = session
        (self._settings.tmp_dir / sid).mkdir(parents=True, exist_ok=True)
        return session

    def get_session(self, sid: str | None) -> SessionData:
        if not sid or sid not in self._sessions:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        session = self._sessions[sid]
        session.touch()
        return session

    def try_get_session(self, sid: str | None) -> SessionData | None:
        if not sid:
            return None
        session = self._sessions.get(sid)
        if not session:
            return None
        session.touch()
        return session

    def remove_session(self, sid: str) -> None:
        session = self._sessions.pop(sid, None)
        if session:
            folder = self._settings.tmp_dir / sid
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)

    def cleanup(self) -> None:
        ttl = timedelta(minutes=self._settings.session_ttl_min)
        now = datetime.utcnow()
        stale = [sid for sid, data in self._sessions.items() if now - data.last_seen > ttl]
        for sid in stale:
            self.remove_session(sid)

    def register_base_image(self, session: SessionData, image_id: str, path: Path) -> None:
        session.base_images[image_id] = path
        session.current_base = image_id

    def get_base_image(self, session: SessionData, image_id: str) -> Path:
        if image_id not in session.base_images:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base image not found")
        return session.base_images[image_id]

    def add_result(self, session: SessionData, result: ResultMeta) -> None:
        session.results[result.result_id] = result
        if session.history.maxlen and len(session.history) == session.history.maxlen:
            oldest_id = session.history.popleft()
            oldest = session.results.pop(oldest_id, None)
            if oldest:
                oldest.path.unlink(missing_ok=True)
        session.history.append(result.result_id)

    def pop_history(self, session: SessionData) -> ResultMeta:
        if len(session.history) <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нет предыдущего результата")
        session.history.pop()
        previous_id = session.history[-1]
        return session.results[previous_id]

    def issue_download_token(self, session: SessionData, result_id: str) -> str:
        result = session.results.get(result_id)
        if result is None:
            raise ValueError(f"Result {result_id} not found for token issuance")
        token = secrets.token_urlsafe(16)
        session.download_tokens[token] = result
        return token

    def consume_download_token(self, session: SessionData, token: str) -> ResultMeta:
        result = session.download_tokens.pop(token, None)
        if result is None:
            raise ValueError("Invalid token")
        return result


session_store = SessionStore()
