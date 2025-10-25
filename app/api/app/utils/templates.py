from __future__ import annotations

from dataclasses import dataclass
import base64
import io
import re
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class TemplateDefinition:
    label: str
    asset_name: str


def _locate_frontend_assets() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "frontend" / "public" / "assets"
        if candidate.exists():
            return candidate
    return None


ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "templates"
FRONTEND_ASSETS_DIR = _locate_frontend_assets()

TEMPLATE_DEFINITIONS: dict[str, TemplateDefinition] = {
    "template-mountains": TemplateDefinition("Mountains", "pattern1.png"),
    "template-city": TemplateDefinition("City", "pattern2.png"),
    "template-lab": TemplateDefinition("Lab", "pattern3.png"),
    "template-forest": TemplateDefinition("Forest", "pattern4.png"),
}


def _iter_candidate_paths(template_id: str):
    definition = TEMPLATE_DEFINITIONS.get(template_id)
    if not definition:
        return

    if ASSETS_DIR.exists():
        yield ASSETS_DIR / definition.asset_name

    if FRONTEND_ASSETS_DIR is not None:
        yield FRONTEND_ASSETS_DIR / definition.asset_name


def _find_template_asset(template_id: str) -> Path | None:
    for path in _iter_candidate_paths(template_id):
        if path.exists():
            return path
    return None


DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$")


def decode_template_image(data_url: str) -> Image.Image:
    match = DATA_URL_PATTERN.match(data_url.strip())
    if not match:
        raise ValueError("Invalid data URL")

    try:
        raw = base64.b64decode(match.group("data"), validate=True)
    except Exception as exc:
        raise ValueError("Failed to decode template data") from exc

    try:
        with Image.open(io.BytesIO(raw)) as image:
            return image.copy()
    except Exception as exc:
        raise ValueError("Failed to parse template image") from exc


def render_template_placeholder(template_id: str) -> Image.Image:
    definition = TEMPLATE_DEFINITIONS.get(template_id)
    if not definition:
        raise KeyError(template_id)

    path = _find_template_asset(template_id)
    if path:
        with Image.open(path) as image:
            return image.convert("RGB")

    raise FileNotFoundError(f"Template asset for '{template_id}' was not found")
