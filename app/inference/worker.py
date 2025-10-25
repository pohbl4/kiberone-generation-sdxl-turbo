import asyncio
import inspect
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional

try:
    from app.common.safety import augment_negative_prompt, sanitize_prompt
except ModuleNotFoundError:  # pragma: no cover - fallback when executed outside package layout
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

import torch
from diffusers import (
    ControlNetModel,
    DiffusionPipeline,
    StableDiffusionXLControlNetPipeline,
    StableDiffusionXLImg2ImgPipeline,
)

torch.set_float32_matmul_precision("high")
if torch.cuda.is_available():
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True


def _ensure_clip_offload_compatibility() -> None:
    try: 
        import sys
        import transformers
    except Exception:
        return

    def _patch_constructor(cls: type) -> None:
        original_init = cls.__init__
        if "offload_state_dict" in inspect.signature(original_init).parameters:
            return

        def _patched_init(self, *args, offload_state_dict=None, **kwargs):
            return original_init(self, *args, **kwargs)

        cls.__init__ = _patched_init

    module_names = {
        "transformers.models.clip.modeling_clip",
        "transformers.models.clip.modeling_clip_text",
        "transformers.models.clip_text_model",
    }

    for name in list(module_names):
        try:
            __import__(name)
        except Exception:
            continue

    for name, module in list(sys.modules.items()):
        if not name.startswith("transformers.models.clip"):
            continue

        module_names.add(name)

    for name in module_names:
        module = sys.modules.get(name)
        if module is None:
            continue

        for attr in ("CLIPTextModel", "CLIPTextModelWithProjection"):
            cls = getattr(module, attr, None)
            if cls is not None:
                _patch_constructor(cls)


_ensure_clip_offload_compatibility()
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image
import uvicorn

try:
    from .logging_config import setup_logging
except ImportError:
    from logging_config import setup_logging

setup_logging()

APP = FastAPI()
LOGGER = logging.getLogger(__name__)

DEFAULT_NEGATIVE_PROMPT = (
    "text, caption, words, letters, handwriting, watermark, logo, signature, subtitles, "
    "numbers, label, typography, blurry, noisy, lowres, artifacts, (((nsfw))), ((nudity)), "
    "nude, naked, uncensored, explicit sexual content, erotic, porn, pornography, adult content, "
    "fetish, bdsm, bondage, leash, collar, lingerie, underwear, panties, bra, bikini, swimsuit, "
    "see-through, transparent clothing, sheer fabric, latex, leather outfit, harness, thong, g-string, "
    "cleavage, sideboob, underboob, breasts, nipples, areola, cameltoe, bulge, genital, genitals, penis, "
    "phallus, vagina, vulva, clitoris, anus, anal, butt, buttocks, ass, rear, crotch, pubic, pubes, "
    "semen, cum, sperm, ejaculation, orgasm, intercourse, penetration, sexual act, blowjob, oral, handjob, "
    "hand job, fingering, masturbation, self-pleasure, strip, stripper, lapdance, sensual, suggestive pose, "
    "provocative, sexy, lewd, obscene, xxx, 18+, r18, nsfw_art, adult_only, profanity, curse, swear, fuck, shit, "
    "bitch, cock, pussy, dick, slut, whore, hentai"
)


class GenerationConfig(BaseModel):
    prompt: str = ""
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT
    num_inference_steps: int = 6
    guidance_scale: float = 1.5
    strength: float = 0.65
    controlnet_conditioning_scale: float = 1.0
    seed: Optional[int] = None


class PipelineHolder:
    def __init__(self) -> None:
        self._pipeline: Optional[DiffusionPipeline] = None
        self._device = self._select_device()
        LOGGER.info("Using inference device %s", self._device)

    def _select_device(self) -> torch.device:
        preferred = os.getenv("INFERENCE_DEVICE")
        explicit_index = os.getenv("INFERENCE_CUDA_DEVICE")

        def _parse_cuda_device(index: Optional[str]) -> Optional[torch.device]:
            if not index:
                return torch.device("cuda")
            candidate = index.strip()
            if not candidate:
                return torch.device("cuda")
            try:
                return torch.device(candidate)
            except Exception as exc:
                LOGGER.warning("Invalid INFERENCE_CUDA_DEVICE %r (%s); falling back to auto", candidate, exc)
                return None

        if preferred:
            pref = preferred.strip().lower()
            if pref in {"cuda", "gpu"}:
                if torch.cuda.is_available():
                    device = _parse_cuda_device(explicit_index)
                    if device is not None:
                        return device
                    return torch.device("cuda")
                LOGGER.warning(
                    "INFERENCE_DEVICE is set to %s but CUDA is not available; falling back to CPU",
                    preferred,
                )
                return torch.device("cpu")
            if pref in {"cpu"}:
                return torch.device("cpu")
            LOGGER.warning("Unsupported INFERENCE_DEVICE value %r; falling back to auto detection", preferred)

        if torch.cuda.is_available():
            device = _parse_cuda_device(explicit_index)
            if device is not None:
                return device
            return torch.device("cuda")

        return torch.device("cpu")

    def _load_pipeline(self) -> DiffusionPipeline:
        if self._pipeline:
            return self._pipeline

        model_id = self._resolve_identifier(
            "MODEL_ID",
            "stabilityai/sdxl-turbo",
            ("sdxl-turbo",),
        )
        controlnet_id = self._resolve_identifier(
            "CONTROLNET_MODEL_ID",
            None,
            (
                "controlnet-scribble-sdxl-1.0",
                "controlnet-scribble-sdxl",
                "controlnet-sdxl",
                "controlnet-sdxl-1.0",
            ),
        )
        controlnet_subfolder = self._resolve_controlnet_subfolder(controlnet_id) if controlnet_id else None

        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        local_only = self._flag_enabled("HF_LOCAL_FILES_ONLY") or self._flag_enabled("HF_HUB_OFFLINE")

        dtype = torch.float16 if self._device.type == "cuda" else torch.float32

        controlnet = None
        if controlnet_id:
            controlnet_kwargs: dict[str, object] = {
                "torch_dtype": dtype,
                "variant": os.getenv("CONTROLNET_VARIANT", "fp16"),
                "use_safetensors": True,
            }
            if controlnet_subfolder:
                controlnet_kwargs["subfolder"] = controlnet_subfolder
            if hf_token:
                controlnet_kwargs["token"] = hf_token
            if local_only:
                controlnet_kwargs["local_files_only"] = True

            controlnet = ControlNetModel.from_pretrained(controlnet_id, **controlnet_kwargs)

        pipeline_kwargs: dict[str, object] = {
            "torch_dtype": dtype,
            "variant": os.getenv("MODEL_VARIANT", "fp16"),
            "use_safetensors": True,
        }
        if hf_token:
            pipeline_kwargs["token"] = hf_token
        if local_only:
            pipeline_kwargs["local_files_only"] = True

        if controlnet is not None:
            pipeline = StableDiffusionXLControlNetPipeline.from_pretrained(
                model_id,
                controlnet=controlnet,
                **pipeline_kwargs,
            )
        else:
            pipeline = StableDiffusionXLImg2ImgPipeline.from_pretrained(
                model_id,
                **pipeline_kwargs,
            )

        if self._device.type == "cuda":
            pipeline.to("cuda")
            try:
                pipeline.enable_xformers_memory_efficient_attention()
            except Exception:
                pass
        else:
            pipeline.to(self._device)
            if self._has_accelerate():
                try:
                    pipeline.enable_model_cpu_offload()
                except RuntimeError as exc:
                    LOGGER.warning(
                        "Falling back to plain CPU execution: model CPU offload is unavailable (%s)",
                        exc,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "Unable to enable model CPU offload due to %s; continuing without it",
                        exc,
                    )
            else:
                LOGGER.info("accelerate is not installed; running pipeline fully on CPU")

            pipeline.enable_attention_slicing()
            pipeline.enable_vae_tiling()

        pipeline.set_progress_bar_config(disable=True)
        self._pipeline = pipeline
        return pipeline

    def get_pipeline(self) -> DiffusionPipeline:
        return self._load_pipeline()

    @staticmethod
    def _flag_enabled(env_var: str) -> bool:
        value = os.getenv(env_var)
        if value is None:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _has_accelerate() -> bool:
        try:
            import accelerate
        except Exception:
            return False

        return True

    def _resolve_identifier(
        self,
        env_var: str,
        default_id: Optional[str],
        candidate_dirs: Iterable[str],
    ) -> Optional[str]:
        explicit = os.getenv(env_var)
        if explicit:
            return explicit

        for base in self._local_model_bases():
            for candidate in candidate_dirs:
                resolved = base / candidate
                if (resolved / "model_index.json").exists():
                    return str(resolved)

        return default_id

    @staticmethod
    def _local_model_bases() -> list[Path]:
        resolved = Path(__file__).resolve()
        resolved_dir = resolved.parent

        configured_dirs: list[Path] = []

        model_path_env = os.getenv("MODEL_LOCAL_DIRS")
        if model_path_env:
            for raw_path in model_path_env.split(os.pathsep):
                raw_path = raw_path.strip()
                if not raw_path:
                    continue
                expanded = Path(raw_path).expanduser()
                configured_dirs.append(expanded)

        root_candidates: list[Path] = []
        for parent in resolved.parents[:3]:
            if parent not in root_candidates:
                root_candidates.append(parent)

        cwd = Path.cwd()
        if cwd not in root_candidates:
            root_candidates.append(cwd)

        if resolved_dir not in root_candidates:
            root_candidates.insert(0, resolved_dir)

        default_dirs: list[Path] = []
        for base in root_candidates:
            default_dirs.extend(
                [
                    base / "models",
                    base / "sdxl-turbo",
                    base / "sdxl-turbo" / "models",
                    base,
                ]
            )

        candidates: list[Path] = []
        for path in configured_dirs + default_dirs:
            try:
                resolved_path = path.resolve()
            except FileNotFoundError:
                resolved_path = path
            if resolved_path in candidates:
                continue
            if resolved_path.exists():
                candidates.append(resolved_path)

        return candidates

    def _resolve_controlnet_subfolder(self, controlnet_id: str) -> Optional[str]:
        explicit = os.getenv("CONTROLNET_SUBFOLDER")
        if explicit:
            return explicit

        path_like = Path(controlnet_id)
        if path_like.exists() and path_like.is_dir():
            for candidate in ("scribble", "controlnet", "diffusion_pytorch_model"):
                if (path_like / candidate / "config.json").exists():
                    return candidate
            return None
        return None


PIPELINE_HOLDER = PipelineHolder()
PIPELINE_LOCK = asyncio.Lock()


async def get_config(
    prompt: str = Form(""),
    negative_prompt: str = Form(DEFAULT_NEGATIVE_PROMPT),
    num_inference_steps: int = Form(10),
    guidance_scale: float = Form(1.5),
    strength: float = Form(0.65),
    controlnet_conditioning_scale: float = Form(1.0),
    seed: Optional[int] = Form(None),
) -> GenerationConfig:
    return GenerationConfig(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        strength=strength,
        controlnet_conditioning_scale=controlnet_conditioning_scale,
        seed=seed,
    )


@APP.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@APP.post("/generate")
async def generate(
    config: GenerationConfig = Depends(get_config),
    base_image: UploadFile = File(...),
    scribble_image: UploadFile = File(...),
):
    LOGGER.info(
        "Received generation request | steps=%d | guidance=%.2f | strength=%.2f | control=%.2f",
        config.num_inference_steps,
        config.guidance_scale,
        config.strength,
        config.controlnet_conditioning_scale,
    )
    try:
        base_bytes = await base_image.read()
        scribble_bytes = await scribble_image.read()
    finally:
        await base_image.close()
        await scribble_image.close()

    if not base_bytes:
        LOGGER.warning("Received empty base image payload; substituting blank canvas")
        base = Image.new("RGB", (512, 512), color=(255, 255, 255))
    else:
        base = Image.open(BytesIO(base_bytes)).convert("RGB").resize((512, 512))

    if not scribble_bytes:
        LOGGER.warning("Received empty scribble payload; substituting transparent mask")
        scribble = Image.new("RGB", (512, 512))
    else:
        scribble = Image.open(BytesIO(scribble_bytes)).convert("RGB").resize((512, 512))

    pipeline = PIPELINE_HOLDER.get_pipeline()
    has_controlnet = isinstance(pipeline, StableDiffusionXLControlNetPipeline)

    seed = config.seed if config.seed is not None else torch.randint(0, 2**31 - 1, ()).item()
    generator_device = "cuda" if PIPELINE_HOLDER._device.type == "cuda" else "cpu"
    generator = torch.Generator(device=generator_device).manual_seed(seed)

    prompt_input = (config.prompt or "")
    sanitized_prompt, filtered_terms = sanitize_prompt(prompt_input)
    if filtered_terms:
        LOGGER.info("Filtered explicit prompt terms: %s", ", ".join(sorted(filtered_terms)))
    if not sanitized_prompt and prompt_input.strip():
        LOGGER.info("Prompt cleared after removing disallowed content")

    prompt_for_generation = sanitized_prompt
    negative_prompt_override = augment_negative_prompt(config.negative_prompt, filtered_terms)

    def run() -> Image.Image:
        prompt_text = prompt_for_generation.strip()
        if not prompt_text:
            LOGGER.info(
                "Received empty prompt; running pipeline with neutral conditioning"
            )
            prompt_text = "best quality, highly detailed illustration"

        prompt_batch = [prompt_text]
        image_batch = [base]

        requested_steps = config.num_inference_steps
        effective_steps = max(4, requested_steps)
        if effective_steps != requested_steps:
            LOGGER.warning(
                "Received num_inference_steps=%d; increasing to minimum supported value %d",
                requested_steps,
                effective_steps,
            )

        call_kwargs: dict[str, object] = {
            "prompt": prompt_batch,
            "image": image_batch,
            "num_inference_steps": effective_steps,
            "guidance_scale": config.guidance_scale,
            "strength": config.strength,
            "generator": generator,
            "num_images_per_prompt": 1,
        }

        negative_prompt = (negative_prompt_override or "").strip()
        if negative_prompt:
            call_kwargs["negative_prompt"] = [negative_prompt]

        if has_controlnet:
            call_kwargs["control_image"] = [scribble]
            call_kwargs["controlnet_conditioning_scale"] = config.controlnet_conditioning_scale
        scheduler = pipeline.scheduler
        scheduler_device = getattr(pipeline, "_execution_device", None) or getattr(pipeline, "device", None)
        try:
            scheduler.set_timesteps(effective_steps, device=scheduler_device)
        except TypeError:
            scheduler.set_timesteps(effective_steps)
        if hasattr(scheduler, "set_begin_index"):
            scheduler.set_begin_index(0)
        if hasattr(scheduler, "_step_index"):
            scheduler._step_index = None
        if hasattr(scheduler, "_begin_index"):
            scheduler._begin_index = None
        if hasattr(scheduler, "is_scale_input_called"):
            scheduler.is_scale_input_called = False

        result = pipeline(**call_kwargs).images[0]
        return result

    try:
        async with PIPELINE_LOCK:
            image: Image.Image = await asyncio.to_thread(run)
    except Exception as exc:
        LOGGER.exception("Generation failed: %s", exc)
        raise HTTPException(status_code=500, detail={"error": {"message": str(exc)}}) from exc

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=1)
    payload = buffer.getvalue()

    LOGGER.info("Generation finished successfully | seed=%d", seed)

    headers = {"X-Seed": str(seed)}
    return Response(content=payload, media_type="image/png", headers=headers)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("worker:APP", host="0.0.0.0", port=port)
