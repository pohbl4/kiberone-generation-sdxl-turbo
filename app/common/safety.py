from __future__ import annotations

import re
from typing import Iterable, Set

_NSFW_PATTERNS: tuple[str, ...] = (
    r"nsfw",
    r"nsfw_art",
    r"nudes?",
    r"nudity",
    r"naked",
    r"topless",
    r"uncensored",
    r"explicit",
    r"x[\s_-]?rated",
    r"adult[\s_-]*only",
    r"adult[\s_-]*content",
    r"adult[\s_-]*materials?",
    r"porn(?:hub)?",
    r"porno",
    r"pornographic",
    r"pornography",
    r"smut",
    r"fetish",
    r"bdsm",
    r"bondage",
    r"lingerie",
    r"underwear",
    r"pant(?:y|ies)",
    r"bras?",
    r"bikini",
    r"swimsuit",
    r"see[\s_-]?through",
    r"transparent[\s_-]*clothing",
    r"sheer",
    r"latex",
    r"leather[\s_-]*outfits?",
    r"harness",
    r"thongs?",
    r"g[\s_-]?string",
    r"cleavage",
    r"sideboob",
    r"underboob",
    r"boobs?",
    r"boobies",
    r"tits?",
    r"titties",
    r"breasts?",
    r"nipples?",
    r"areolae?",
    r"cameltoe",
    r"bulge",
    r"genitals?",
    r"genitalia",
    r"penis",
    r"phallus",
    r"vagina",
    r"vulva",
    r"clitoris",
    r"anus",
    r"anal",
    r"butts?",
    r"buttocks",
    r"ass",
    r"rear",
    r"crotch",
    r"pubic",
    r"pubes",
    r"semen",
    r"cum",
    r"sperm",
    r"ejaculation",
    r"orgasm",
    r"intercourse",
    r"penetration",
    r"blowjobs?",
    r"oral[\s_-]*sex",
    r"hand[\s_-]*jobs?",
    r"fingering",
    r"masturbation",
    r"self[\s_-]*pleasure",
    r"strip(?:per|tease)?",
    r"lap[\s_-]*dance",
    r"sensual",
    r"suggestive",
    r"provocative",
    r"sexy",
    r"lewd",
    r"obscene",
    r"xxx",
    r"18\+",
    r"r18",
    r"hentai",
    r"yaoi",
    r"yuri",
    r"fuck",
    r"shit",
    r"bitch",
    r"cock",
    r"pussy",
    r"dick",
    r"slut",
    r"whore",
)

_NSFW_REGEX = re.compile(r"(?i)(?<!\w)(?:" + "|".join(_NSFW_PATTERNS) + r")(?!\w)")

__all__ = [
    "augment_negative_prompt",
    "detect_nsfw_terms",
    "sanitize_prompt",
]


def _canonical(term: str) -> str:
    normalized = re.sub(r"\s+", " ", term.strip().lower())
    return normalized


def detect_nsfw_terms(text: str) -> Set[str]:
    if not text:
        return set()
    return { _canonical(match.group(0)) for match in _NSFW_REGEX.finditer(text) }


def sanitize_prompt(prompt: str) -> tuple[str, Set[str]]:
    if not prompt:
        return "", set()

    matches = detect_nsfw_terms(prompt)
    if not matches:
        return prompt.strip(), set()

    sanitized = _NSFW_REGEX.sub(" ", prompt)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized, matches


def augment_negative_prompt(base: str, terms: Iterable[str]) -> str:
    extra_terms: Set[str] = set()
    for term in terms:
        cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", term.lower()).strip("_")
        if not cleaned:
            continue
        extra_terms.add(cleaned)

    if not extra_terms:
        return base

    extra_terms.update({"nsfw", "uncensored", "explicit"})
    weighted = ", ".join(f"(({token}:1.8))" for token in sorted(extra_terms))

    base = (base or "").strip()
    if base:
        return f"{base}, {weighted}"
    return weighted
