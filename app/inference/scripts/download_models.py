from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from huggingface_hub import snapshot_download


@dataclass(frozen=True)
class ModelSpec:
    name: str
    repo_id: str
    relative_dir: str
    allow_patterns: tuple[str, ...] | None = None


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_DIR = REPO_ROOT / "sdxl-turbo" / "models"

DEFAULT_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="SDXL Turbo base",
        repo_id=os.getenv("MODEL_ID", "stabilityai/sdxl-turbo"),
        relative_dir="sdxl-turbo",
        allow_patterns=None,
    ),
    ModelSpec(
        name="ControlNet scribble",
        repo_id=os.getenv("CONTROLNET_MODEL_ID", "diffusers/controlnet-sdxl-1.0"),
        relative_dir="controlnet-scribble-sdxl-1.0",
        allow_patterns=(
            "model_index.json",
            "README.md",
            "config.json",
            "scribble/*",
            "scheduler/*",
            "diffusion_pytorch_model.*",
            "*tokenizer*/**",
            "feature_extractor/**",
        ),
    ),
)


def download(spec: ModelSpec, *, base_dir: Path, token: str | None, local_only: bool, revision: str | None) -> Path:
    destination = base_dir / spec.relative_dir
    destination.mkdir(parents=True, exist_ok=True)

    marker = destination / "model_index.json"
    if marker.exists():
        print(f"[skip] {spec.name} already present at {destination}")
        return destination

    print(f"[download] Fetching {spec.name} → {destination}")
    snapshot_download(
        repo_id=spec.repo_id,
        local_dir=destination,
        local_dir_use_symlinks=False,
        token=token,
        local_files_only=local_only,
        revision=revision,
        allow_patterns=spec.allow_patterns,
    )
    return destination


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SDXL Turbo and ControlNet weights into the local repository",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help="Directory used to store downloaded models (default: sdxl-turbo/models)",
    )
    parser.add_argument(
        "--no-base",
        action="store_true",
        help="Skip downloading the base SDXL Turbo model",
    )
    parser.add_argument(
        "--no-controlnet",
        action="store_true",
        help="Skip downloading the ControlNet model",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("HUGGINGFACE_TOKEN"),
        help="Hugging Face access token (defaults to HUGGINGFACE_TOKEN env var)",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Use only local cache entries (do not hit the network)",
    )
    parser.add_argument(
        "--revision",
        type=str,
        default=None,
        help="Optional model revision to download",
    )
    parser.add_argument(
        "--controlnet-subfolder",
        type=str,
        default="scribble",
        help="ControlNet subfolder to reference in runtime environments (default: scribble)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    args.base_dir.mkdir(parents=True, exist_ok=True)

    selected: list[ModelSpec] = []
    for spec in DEFAULT_MODELS:
        if spec.relative_dir.startswith("sdxl") and args.no_base:
            continue
        if spec.relative_dir.startswith("controlnet") and args.no_controlnet:
            continue
        selected.append(spec)

    if not selected:
        print("Nothing to download; both base and ControlNet models were skipped.")
        return 0

    for spec in selected:
        try:
            download(
                spec,
                base_dir=args.base_dir,
                token=args.token,
                local_only=args.local_files_only,
                revision=args.revision,
            )
        except Exception as exc:  # pragma: no cover - network/hub errors
            print(f"[error] Failed to download {spec.name}: {exc}", file=sys.stderr)
            return 1

    controlnet_hint = (
        f"Remember to set CONTROLNET_SUBFOLDER={args.controlnet_subfolder} when starting the worker"
        if not args.no_controlnet
        else None
    )
    if controlnet_hint:
        print(controlnet_hint)
    print(f"Models stored under: {args.base_dir}")
    print(
        "Add this directory to MODEL_LOCAL_DIRS or leave it in place to be auto-discovered by the worker."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
