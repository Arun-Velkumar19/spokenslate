"""Settings from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    compile_model: str
    alt_model: str
    camera_index: int
    mic_device: str | None
    target: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_key=os.getenv("META_API_KEY", ""),
        base_url=os.getenv("META_API_BASE_URL", ""),
        compile_model=os.getenv("PAPEROS_COMPILE_MODEL", "muse-spark-1.1"),
        alt_model=os.getenv("PAPEROS_ALT_MODEL", "muse-wonder-1.0"),
        camera_index=int(os.getenv("PAPEROS_CAMERA_INDEX", "0")),
        mic_device=os.getenv("PAPEROS_MIC_DEVICE") or None,
        target=os.getenv("PAPEROS_TARGET", "bitrun"),
    )
