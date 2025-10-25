from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_pass: str = Field("admin", alias="AUTH_PASS")
    session_secret: str = Field("dev-session-secret", alias="SESSION_SECRET")
    session_ttl_min: int = Field(30, alias="SESSION_TTL_MIN")
    session_cleanup_interval_seconds: int = Field(60, alias="SESSION_CLEANUP_INTERVAL_SECONDS")
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")
    tmp_dir: Path = Field(Path("/tmp/kiberone"), alias="TMP_DIR")
    log_dir: Path = Field(Path("logs"), alias="LOG_DIR")
    inference_url: str = Field("http://127.0.0.1:8080", alias="INFERENCE_URL")
    inference_timeout_seconds: int = Field(120, alias="INFERENCE_TIMEOUT_SECONDS")
    inference_host_aliases_raw: str = Field("", alias="INFERENCE_HOST_ALIASES")
    inference_connect_attempts: int = Field(3, alias="INFERENCE_CONNECT_ATTEMPTS")
    inference_connect_backoff_seconds: float = Field(0.75, alias="INFERENCE_CONNECT_BACKOFF_SECONDS")
    max_upload_mb: int = Field(10, alias="MAX_UPLOAD_MB")
    max_parallel_jobs_per_session: int = Field(2, alias="MAX_PARALLEL_JOBS_PER_SESSION")
    queue_overload_threshold: int = Field(3, alias="QUEUE_OVERLOAD_THRESHOLD")
    queue_recovery_threshold: int = Field(1, alias="QUEUE_RECOVERY_THRESHOLD")
    target_latency_seconds: float = Field(2.5, alias="TARGET_LATENCY_SECONDS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def inference_host_aliases(self) -> list[str]:
        raw = self.inference_host_aliases_raw.strip()
        if not raw:
            return []
        aliases = [
            token.strip()
            for token in raw.replace(";", ",").split(",")
            if token.strip()
        ]
        return aliases


class QualityPreset(BaseModel):
    name: str
    num_inference_steps: int
    guidance_scale: float
    strength: float
    controlnet_conditioning_scale: float = 1.0


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[arg-type]
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings


QUALITY_PRESETS: dict[str, QualityPreset] = {
    "fast": QualityPreset(name="fast", num_inference_steps=6, guidance_scale=1, strength=0.65),
    "normal": QualityPreset(name="normal", num_inference_steps=6, guidance_scale=1, strength=0.65),
    "high": QualityPreset(name="high", num_inference_steps=6, guidance_scale=1.5, strength=0.75),
}

QUALITY_FALLBACKS: dict[str, str] = {
    "high": "normal",
    "normal": "fast",
    "fast": "fast",
}

NEGATIVE_PROMPT = (
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
