from __future__ import annotations

import secrets

from io import BytesIO

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi import status as http_status

from ..config import QUALITY_PRESETS, get_settings
from ..jobs import job_manager
from ..sessions import SessionData, session_store
from ..utils.images import composite_base_with_sketch, extract_sketch_layers, load_canvas_image
from ..utils.translation import normalize_prompt
from .auth import get_session

router = APIRouter(tags=["generate"])


@router.post("/generate")
async def generate_image(
    base_image_id: str = Form(...),
    prompt: str = Form(""),
    quality: str = Form("normal"),
    ui_language: str | None = Form(None),
    request_id: str | None = Form(None),
    seed: int | None = Form(None),
    sketch_png: UploadFile = File(...),
    canvas_png: UploadFile | None = File(None),
    session: SessionData = Depends(get_session),
):
    settings = get_settings()
    if quality not in QUALITY_PRESETS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_QUALITY", "message": "Invalid quality preset"}},
        )

    try:
        base_path = session_store.get_base_image(session, base_image_id)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        sketch_data = await sketch_png.read()
        canvas_data = await canvas_png.read() if canvas_png is not None else None
    finally:
        await sketch_png.close()
        if canvas_png is not None:
            await canvas_png.close()

    scribble, sketch_rgba = extract_sketch_layers(sketch_data)
    if scribble.getbbox() is None:
        return {"status": "skipped"}
    sketch_id = request_id or f"sketch_{secrets.token_hex(8)}"
    session_dir = settings.tmp_dir / session.sid
    session_dir.mkdir(parents=True, exist_ok=True)
    mask_name = f"{sketch_id}_mask.png"
    canvas_name = f"{sketch_id}_canvas.png"
    mask_buffer = BytesIO()
    scribble.save(mask_buffer, format="PNG", optimize=False, compress_level=1)
    mask_bytes = mask_buffer.getvalue()

    if canvas_data:
        try:
            composite_image = load_canvas_image(canvas_data, background_path=base_path)
        except Exception as exc:  # pragma: no cover - invalid payload
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_CANVAS", "message": "Некорректное изображение канваса"}},
            ) from exc
    else:
        composite_image = composite_base_with_sketch(base_path, sketch_rgba)
    canvas_buffer = BytesIO()
    composite_image.save(canvas_buffer, format="PNG", optimize=False, compress_level=1)
    canvas_bytes = canvas_buffer.getvalue()

    translated_prompt = await normalize_prompt(prompt, ui_language)

    try:
        job = await job_manager.submit_job(
            session=session,
            base_bytes=canvas_bytes,
            sketch_bytes=mask_bytes,
            base_name=canvas_name,
            sketch_name=mask_name,
            prompt=translated_prompt,
            quality=quality,
            seed=seed,
        )
    except RuntimeError:
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "TOO_MANY_JOBS", "message": "Слишком много параллельных задач"}},
        )

    return {
        "job_id": job.job_id,
        "status": "queued",
        "quality_effective": job.quality_effective,
        "quality_degraded": job.degraded,
    }


@router.post("/generate/cancel")
async def cancel_generation(
    payload: dict = Body(...),
    session: SessionData = Depends(get_session),
):
    job_id = payload.get("job_id") if isinstance(payload, dict) else None
    if not job_id or not isinstance(job_id, str):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_JOB_ID", "message": "Некорректный идентификатор задачи"}},
        )

    status = await job_manager.cancel_job(session, job_id)
    if status == "not_found":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Задача не найдена"}},
        )

    return {"status": status}


@router.get("/generate/status/{job_id}")
async def get_generation_status(job_id: str, session: SessionData = Depends(get_session)):
    return job_manager.snapshot(session, job_id)
