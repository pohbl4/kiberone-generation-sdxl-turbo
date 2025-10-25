from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .config import get_settings
from .logging_config import setup_logging
from .routers import auth, canvas, generate, health, history, images, results, upload, ws
from .sessions import session_store

setup_logging()

settings = get_settings()


async def _cleanup_loop(interval: int) -> None:
    try:
        while True:
            session_store.cleanup()
            await asyncio.sleep(max(1, interval))
    except asyncio.CancelledError:
        session_store.cleanup()
        raise


@asynccontextmanager
async def _lifespan(app: FastAPI):
    cleanup_task: asyncio.Task[None] | None = None
    try:
        cleanup_task = asyncio.create_task(_cleanup_loop(settings.session_cleanup_interval_seconds))
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task


app = FastAPI(default_response_class=ORJSONResponse, lifespan=_lifespan)

allowed_origins = {
    "https://kiberone-generation.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(canvas.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(ws.router)
