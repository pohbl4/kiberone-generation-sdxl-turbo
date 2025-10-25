from __future__ import annotations

import asyncio
import base64
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List, Optional, Set
from urllib.parse import ParseResult, urlparse, urlunparse

from fastapi import HTTPException, WebSocket, status
import httpx

try:
    from app.common.safety import augment_negative_prompt, sanitize_prompt
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    candidates = [here, here.parent, here.parent.parent]
    for candidate in candidates:
        if candidate.exists():
            path_str = str(candidate)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
    from app.common.safety import augment_negative_prompt, sanitize_prompt
from .config import NEGATIVE_PROMPT, QUALITY_FALLBACKS, QUALITY_PRESETS, get_settings
from .sessions import ResultMeta, SessionData, session_store


LOGGER = logging.getLogger(__name__)


@dataclass
class Job:
    job_id: str
    session: SessionData
    base_bytes: bytes
    sketch_bytes: bytes
    base_name: str
    sketch_name: str
    prompt: str
    quality_requested: str
    quality_effective: str
    created_at: datetime
    negative_prompt: str
    listeners: Set[WebSocket] = field(default_factory=set)
    status: str = "queued"
    seed: Optional[int] = None
    result_path: Optional[Path] = None
    error_message: Optional[str] = None
    degraded: bool = False
    cancelled: bool = False
    download_token: Optional[str] = None
    filtered_terms: Set[str] = field(default_factory=set)


class JobManager:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._jobs: Dict[str, Job] = {}
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._latencies: List[float] = []
        self._queue_lock = asyncio.Lock()
        self._active_job: Optional[Job] = None
        self._active_task: Optional[asyncio.Task[None]] = None
        self._degrade_active = False
        self._http_client: Optional[httpx.AsyncClient] = None

    def _ensure_worker(self) -> None:
        if not self._worker_task or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            timeout_seconds = self._settings.inference_timeout_seconds
            timeout = httpx.Timeout(timeout_seconds)
            self._http_client = httpx.AsyncClient(timeout=timeout, trust_env=False)
        return self._http_client

    async def _worker_loop(self) -> None:
        while True:
            job = await self._queue.get()
            self._active_job = job
            start = time.perf_counter()
            cancelled_pre_run = job.cancelled
            try:
                if cancelled_pre_run:
                    if job.status != "cancelled":
                        await self._set_status(job, "cancelled")
                else:
                    await self._set_status(job, "running")
                    self._active_task = asyncio.create_task(self._produce_result(job))
                    if job.cancelled and not self._active_task.done():
                        self._active_task.cancel()
                    try:
                        await self._active_task
                        if job.cancelled:
                            await self._set_status(job, "cancelled")
                        else:
                            await self._set_status(job, "done")
                    except asyncio.CancelledError:
                        job.cancelled = True
                        await self._set_status(job, "cancelled")
                    except Exception as exc:
                        job.error_message = str(exc)
                        await self._set_status(job, "error")
            finally:
                self._active_task = None
                self._queue.task_done()
                elapsed = time.perf_counter() - start
                self._latencies.append(elapsed)
                if len(self._latencies) > 50:
                    self._latencies.pop(0)
                if job.job_id in job.session.active_jobs:
                    job.session.active_jobs.remove(job.job_id)
                self._active_job = None
                self._evaluate_degrade_mode()

    async def _set_status(self, job: Job, status: str) -> None:
        job.status = status
        payload: dict[str, object] = {
            "type": "status" if status in {"queued", "running"} else status,
            "job_id": job.job_id,
            "value": status,
            "quality_effective": job.quality_effective,
            "quality_degraded": job.degraded,
        }
        if status == "done" and job.result_path:
            if job.download_token is None:
                job.download_token = session_store.issue_download_token(job.session, job.job_id)
            payload = {
                "type": "result",
                "job_id": job.job_id,
                "result_url": f"/api/result/{job.result_path.name}",
                "seed": job.seed,
                "quality_effective": job.quality_effective,
                "quality_degraded": job.degraded,
                "download_token": job.download_token,
            }
        if status == "error":
            payload = {
                "type": "error",
                "job_id": job.job_id,
                "message": job.error_message or "Ошибка",
            }
        await self._notify(job, payload)

    async def _notify(self, job: Job, payload: dict[str, object]) -> None:
        listeners = list(job.listeners)
        for ws in listeners:
            try:
                await ws.send_json(payload)
            except Exception:
                job.listeners.discard(ws)

    def _queue_depth(self) -> int:
        return self._queue.qsize() + (1 if self._active_job else 0)

    async def cancel_job(self, session: SessionData, job_id: str) -> str:
        job = self._jobs.get(job_id)
        if not job or job.session.sid != session.sid:
            return "not_found"

        if job.status in {"done", "error", "cancelled"}:
            return "completed"

        job.cancelled = True
        job.session.active_jobs.discard(job.job_id)

        if job.status == "queued":
            await self._set_status(job, "cancelled")
            return "cancelled"

        if job.status == "running" and self._active_job and self._active_job.job_id == job_id:
            if self._active_task and not self._active_task.done():
                self._active_task.cancel()
            return "cancelled"

        return "cancelled"

    def _evaluate_degrade_mode(self, pending: int = 0) -> bool:
        queue_depth = self._queue_depth() + pending
        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

        if self._degrade_active:
            if queue_depth <= self._settings.queue_recovery_threshold and avg_latency <= self._settings.target_latency_seconds:
                self._degrade_active = False
        else:
            if queue_depth >= self._settings.queue_overload_threshold or (
                queue_depth > 0 and avg_latency > self._settings.target_latency_seconds
            ):
                self._degrade_active = True
        return self._degrade_active

    async def _produce_result(self, job: Job) -> None:
        seed = secrets.randbelow(2**31 - 1) if job.seed is None else job.seed
        job.seed = seed
        settings = get_settings()
        preset = QUALITY_PRESETS[job.quality_effective]
        inference_urls = self._build_inference_urls(settings.inference_url)
        if not inference_urls:
            raise RuntimeError("Inference URL is not configured")

        data = {
            "prompt": job.prompt,
            "negative_prompt": job.negative_prompt,
            "num_inference_steps": str(preset.num_inference_steps),
            "guidance_scale": str(preset.guidance_scale),
            "strength": str(preset.strength),
            "controlnet_conditioning_scale": str(preset.controlnet_conditioning_scale),
            "seed": str(seed),
        }

        timeout_seconds = settings.inference_timeout_seconds
        client = self._get_http_client()
        response: Optional[httpx.Response] = None
        last_error: Optional[Exception] = None
        error_details: list[str] = []

        attempts = max(1, settings.inference_connect_attempts)
        backoff = settings.inference_connect_backoff_seconds
        if backoff < 0:
            backoff = 0.0

        timeout_abort = False

        for url in inference_urls:
            timeout_abort = False
            response = None
            for attempt in range(1, attempts + 1):
                try:
                    files = {
                        "base_image": (job.base_name, job.base_bytes, "image/png"),
                        "scribble_image": (job.sketch_name, job.sketch_bytes, "image/png"),
                    }
                    response = await client.post(url, data=data, files=files)
                    break
                except httpx.TimeoutException as exc:
                    last_error = exc
                    timeout_abort = True
                    error_details.append(
                        f"{url} (attempt {attempt}/{attempts}): timed out after {timeout_seconds} seconds"
                    )
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
                    error_details.append(f"{url} (attempt {attempt}/{attempts}): {exc}")
                    if attempt < attempts and backoff:
                        await asyncio.sleep(backoff)
            if response is not None or timeout_abort:
                break

        if response is None:
            attempted = ", ".join(inference_urls)
            if timeout_abort and isinstance(last_error, httpx.TimeoutException):
                message = "Inference timed out"
            elif error_details:
                message = "; ".join(error_details)
            else:
                message = str(last_error) if last_error else "Inference connection failed"
            raise RuntimeError(f"All inference endpoints failed ({attempted}): {message}")

        if response.status_code == 429:
            raise RuntimeError("Inference overloaded")

        if response.status_code >= 400:
            message = response.text
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    detail = response.json().get("error")
                    if isinstance(detail, dict):
                        message = detail.get("message", message)
                except Exception:
                    pass
            raise RuntimeError(message or "Inference failed")

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            payload = response.json()
            seed_from_worker = payload.get("seed")
            if isinstance(seed_from_worker, int):
                job.seed = seed_from_worker
            elif isinstance(seed_from_worker, str) and seed_from_worker.isdigit():
                job.seed = int(seed_from_worker)
            image_b64 = payload.get("image_base64")
            if not image_b64:
                raise RuntimeError("Invalid inference response")
            image_bytes = base64.b64decode(image_b64)
        elif content_type.startswith("image/"):
            seed_header = response.headers.get("x-seed") or response.headers.get("X-Seed")
            if seed_header and seed_header.isdigit():
                job.seed = int(seed_header)
            image_bytes = response.content
            if not image_bytes:
                raise RuntimeError("Empty inference payload")
        else:
            raise RuntimeError("Unsupported inference response type")

        output_dir = settings.tmp_dir / job.session.sid
        output_dir.mkdir(parents=True, exist_ok=True)
        result_path = output_dir / f"result_{job.job_id}.png"
        result_path.write_bytes(image_bytes)
        job.result_path = result_path
        job.base_bytes = b""
        job.sketch_bytes = b""

        meta = ResultMeta(
            result_id=job.job_id,
            path=result_path,
            seed=job.seed,
            quality_requested=job.quality_requested,
            quality_effective=job.quality_effective,
            created_at=datetime.utcnow(),
        )
        session_store.add_result(job.session, meta)

    def _effective_quality(self, requested: str) -> tuple[str, bool]:
        if not self._evaluate_degrade_mode(pending=1):
            return requested, False
        effective = QUALITY_FALLBACKS.get(requested, requested)
        degraded = effective != requested
        return effective, degraded

    def _build_inference_urls(self, base_url: str) -> List[str]:
        raw = (base_url or "").strip()

        if not raw:
            return []

        parts = [
            token.strip()
            for token in re.split(r"[,\s]+", raw)
            if token.strip()
        ]

        if not parts:
            return []

        def ensure_generate(url: str) -> str:
            return url if url.endswith("/generate") else f"{url}/generate"

        def normalise(part: str) -> str:
            candidate = part
            if "://" not in candidate:
                candidate = f"http://{candidate}"
            return ensure_generate(candidate.rstrip("/"))

        candidates: List[str] = []

        for part in parts:
            base = normalise(part)
            if base not in candidates:
                candidates.append(base)

            try:
                parsed = urlparse(base)
            except ValueError:
                continue

            host = parsed.hostname or ""
            if not host:
                continue

            alt_hosts: List[str] = []
            loopback_hosts = ["127.0.0.1", "localhost", "0.0.0.0", "::1"]
            if host in loopback_hosts:
                alt_hosts.extend(h for h in loopback_hosts if h != host)
                alt_hosts.extend([
                    "inference",
                    "inference.local",
                    "worker",
                    "gpu",
                    "host.docker.internal",
                ])

            extra_hosts_env = self._settings.inference_host_aliases
            for extra in extra_hosts_env:
                if extra not in alt_hosts and extra != host:
                    alt_hosts.append(extra)

            def format_netloc(hostname: str, port: Optional[int]) -> str:
                if not hostname:
                    return ""
                needs_brackets = ":" in hostname and not hostname.startswith("[")
                host_part = f"[{hostname}]" if needs_brackets else hostname
                if port is None:
                    return host_part
                return f"{host_part}:{port}"

            for alt in alt_hosts:
                netloc = format_netloc(alt, parsed.port)
                if not netloc:
                    continue
                alt_parsed = ParseResult(
                    scheme=parsed.scheme,
                    netloc=netloc,
                    path=parsed.path,
                    params=parsed.params,
                    query=parsed.query,
                    fragment=parsed.fragment,
                )
                alt_url = ensure_generate(urlunparse(alt_parsed).rstrip("/"))
                if alt_url not in candidates:
                    candidates.append(alt_url)

        return candidates

    async def submit_job(
        self,
        session: SessionData,
        base_bytes: bytes,
        sketch_bytes: bytes,
        base_name: str,
        sketch_name: str,
        prompt: str,
        quality: str,
        seed: Optional[int] = None,
    ) -> Job:
        if len(session.active_jobs) >= self._settings.max_parallel_jobs_per_session:
            raise RuntimeError("Too many concurrent jobs")
        job_id = f"job_{secrets.token_hex(8)}"
        effective_quality, degraded = self._effective_quality(quality)

        sanitized_prompt, filtered_terms = sanitize_prompt(prompt)
        negative_prompt = augment_negative_prompt(NEGATIVE_PROMPT, filtered_terms)

        if filtered_terms:
            LOGGER.info(
                "Filtered explicit terms for job %s: %s",
                job_id,
                ", ".join(sorted(filtered_terms)),
            )
        if not sanitized_prompt and prompt.strip():
            LOGGER.info("Prompt for job %s cleared after removing disallowed content", job_id)

        job = Job(
            job_id=job_id,
            session=session,
            base_bytes=base_bytes,
            sketch_bytes=sketch_bytes,
            base_name=base_name,
            sketch_name=sketch_name,
            prompt=sanitized_prompt,
            quality_requested=quality,
            quality_effective=effective_quality,
            created_at=datetime.utcnow(),
            negative_prompt=negative_prompt,
            seed=seed,
            degraded=degraded,
            filtered_terms=set(filtered_terms),
        )
        self._jobs[job_id] = job
        session.active_jobs.add(job_id)
        await self._queue.put(job)
        self._ensure_worker()
        await self._set_status(job, "queued")
        return job

    def get_job(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def snapshot(self, session: SessionData, job_id: str) -> dict[str, object]:
        job = self._jobs.get(job_id)
        if not job or job.session.sid != session.sid:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        if job.status == "done" and job.result_path and job.download_token is None:
            job.download_token = session_store.issue_download_token(job.session, job.job_id)

        result_url = f"/api/result/{job.result_path.name}" if job.result_path else None

        return {
            "job_id": job.job_id,
            "status": job.status,
            "quality_effective": job.quality_effective,
            "quality_degraded": job.degraded,
            "seed": job.seed,
            "result_url": result_url,
            "download_token": job.download_token,
            "error_message": job.error_message,
        }

    async def subscribe(self, job_id: str, websocket: WebSocket) -> None:
        job = self._jobs.get(job_id)
        if not job:
            await websocket.send_json({"type": "error", "job_id": job_id, "message": "Job not found"})
            return
        job.listeners.add(websocket)
        await websocket.send_json(
            {
                "type": "status",
                "job_id": job.job_id,
                "value": job.status,
                "quality_effective": job.quality_effective,
                "quality_degraded": job.degraded,
            }
        )
        if job.status == "done" and job.result_path:
            await websocket.send_json(
                {
                    "type": "result",
                    "job_id": job.job_id,
                    "result_url": f"/api/result/{job.result_path.name}",
                    "seed": job.seed,
                    "quality_effective": job.quality_effective,
                    "quality_degraded": job.degraded,
                    "download_token": session_store.issue_download_token(job.session, job.job_id),
                }
            )
        elif job.status == "error":
            await websocket.send_json(
                {
                    "type": "error",
                    "job_id": job.job_id,
                    "message": job.error_message or "Ошибка",
                }
            )


job_manager = JobManager()
