from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


CANVAS_SIZE = 512


def normalize_base_image(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as img:
        img = img.convert("RGB")
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        scale = min(CANVAS_SIZE / width, CANVAS_SIZE / height)
        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0))
        offset_x = (CANVAS_SIZE - new_width) // 2
        offset_y = (CANVAS_SIZE - new_height) // 2
        canvas.paste(resized, (offset_x, offset_y))
        left_pad = offset_x
        top_pad = offset_y
        right_pad = CANVAS_SIZE - (offset_x + new_width)
        bottom_pad = CANVAS_SIZE - (offset_y + new_height)

        if left_pad > 0:
            left_strip = resized.crop((0, 0, 1, new_height))
            left_strip = left_strip.resize((left_pad, new_height), Image.Resampling.NEAREST)
            canvas.paste(left_strip, (0, offset_y))

        if right_pad > 0:
            right_strip = resized.crop((new_width - 1, 0, new_width, new_height))
            right_strip = right_strip.resize((right_pad, new_height), Image.Resampling.NEAREST)
            canvas.paste(right_strip, (offset_x + new_width, offset_y))

        if top_pad > 0:
            top_strip = resized.crop((0, 0, new_width, 1))
            top_strip = top_strip.resize((new_width, top_pad), Image.Resampling.NEAREST)
            canvas.paste(top_strip, (offset_x, 0))

        if bottom_pad > 0:
            bottom_strip = resized.crop((0, new_height - 1, new_width, new_height))
            bottom_strip = bottom_strip.resize((new_width, bottom_pad), Image.Resampling.NEAREST)
            canvas.paste(bottom_strip, (offset_x, offset_y + new_height))

        if left_pad > 0 and top_pad > 0:
            top_left_colour = resized.getpixel((0, 0))
            top_left_patch = Image.new("RGB", (left_pad, top_pad), top_left_colour)
            canvas.paste(top_left_patch, (0, 0))

        if right_pad > 0 and top_pad > 0:
            top_right_colour = resized.getpixel((new_width - 1, 0))
            top_right_patch = Image.new("RGB", (right_pad, top_pad), top_right_colour)
            canvas.paste(top_right_patch, (offset_x + new_width, 0))

        if left_pad > 0 and bottom_pad > 0:
            bottom_left_colour = resized.getpixel((0, new_height - 1))
            bottom_left_patch = Image.new("RGB", (left_pad, bottom_pad), bottom_left_colour)
            canvas.paste(bottom_left_patch, (0, offset_y + new_height))

        if right_pad > 0 and bottom_pad > 0:
            bottom_right_colour = resized.getpixel((new_width - 1, new_height - 1))
            bottom_right_patch = Image.new("RGB", (right_pad, bottom_pad), bottom_right_colour)
            canvas.paste(bottom_right_patch, (offset_x + new_width, offset_y + new_height))

        return canvas


def _sketch_rgba(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as img:
        return img.convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.NEAREST)


def extract_sketch_layers(data: bytes) -> tuple[Image.Image, Image.Image]:
    rgba = _sketch_rgba(data)
    arr = np.array(rgba)
    alpha = arr[..., 3]
    lines = (alpha > 0).astype(np.uint8) * 255
    scribble = Image.fromarray(lines, mode="L").filter(ImageFilter.GaussianBlur(radius=1))
    return scribble, rgba


def scribble_from_sketch(data: bytes) -> Image.Image:
    scribble, _ = extract_sketch_layers(data)
    return scribble


def composite_base_with_sketch(base_path: Path, sketch_rgba: Image.Image) -> Image.Image:
    with Image.open(base_path) as base_img:
        base = base_img.convert("RGBA")

    canvas = Image.new("RGBA", base.size)
    canvas.alpha_composite(base)
    canvas.alpha_composite(sketch_rgba)
    return canvas.convert("RGB")


def load_canvas_image(data: bytes, *, background_path: Path | None = None) -> Image.Image:
    with Image.open(BytesIO(data)) as img:
        canvas = img.convert("RGBA")

    if canvas.size != (CANVAS_SIZE, CANVAS_SIZE):
        canvas = canvas.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)

    if background_path is not None:
        with Image.open(background_path) as base_img:
            background = base_img.convert("RGBA")
        if background.size != (CANVAS_SIZE, CANVAS_SIZE):
            background = background.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
    else:
        background = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 255))

    output = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    output.alpha_composite(background)
    output.alpha_composite(canvas)
    return output.convert("RGB")
