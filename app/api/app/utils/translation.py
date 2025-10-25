from __future__ import annotations

import re
from typing import Optional

import asyncio
from collections import OrderedDict

import httpx

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


TRANSLATION_CACHE: "OrderedDict[str, str]" = OrderedDict()
TRANSLATION_CACHE_LOCK = asyncio.Lock()
TRANSLATION_CACHE_SIZE = 128
_TRANSLATE_CLIENT: httpx.AsyncClient | None = None


def _get_translate_client() -> httpx.AsyncClient:
    global _TRANSLATE_CLIENT
    if _TRANSLATE_CLIENT is None:
        timeout = httpx.Timeout(5.0)
        _TRANSLATE_CLIENT = httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False)
    return _TRANSLATE_CLIENT


async def _get_cached_translation(text: str) -> str | None:
    async with TRANSLATION_CACHE_LOCK:
        result = TRANSLATION_CACHE.get(text)
        if result is not None:
            TRANSLATION_CACHE.move_to_end(text)
        return result


async def _store_cached_translation(text: str, translation: str) -> None:
    async with TRANSLATION_CACHE_LOCK:
        TRANSLATION_CACHE[text] = translation
        TRANSLATION_CACHE.move_to_end(text)
        while len(TRANSLATION_CACHE) > TRANSLATION_CACHE_SIZE:
            TRANSLATION_CACHE.popitem(last=False)


async def translate_to_english(text: str) -> str:
    if not text.strip():
        return text
    cached = await _get_cached_translation(text)
    if cached is not None:
        return cached
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "en",
        "dt": "t",
        "q": text,
    }
    try:
        client = _get_translate_client()
        response = await client.get(TRANSLATE_URL, params=params)
        if response.status_code != 200:
            return text
        data = response.json()
    except Exception:
        return text
    if not isinstance(data, list) or not data:
        return text
    segments = data[0]
    if not isinstance(segments, list):
        return text
    translated_parts: list[str] = []
    for segment in segments:
        if isinstance(segment, list) and segment:
            part = segment[0]
            if isinstance(part, str):
                translated_parts.append(part)
    translated = "".join(translated_parts).strip()
    result = translated or text
    await _store_cached_translation(text, result)
    return result


async def normalize_prompt(prompt: str, ui_language: Optional[str] = None) -> str:
    if not prompt:
        return prompt
    if ui_language and ui_language.lower().startswith("ru"):
        return await translate_to_english(prompt)
    if CYRILLIC_RE.search(prompt):
        return await translate_to_english(prompt)
    return prompt
