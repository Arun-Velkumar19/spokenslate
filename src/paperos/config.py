"""Settings from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://api.meta.ai/v1"
    # Seed models (playground-verified Oct 27: muse-spark-1.3 resolved 10/10 references)
    board_model: str = "muse-spark-1.3"      # reads the board each keyframe
    resolve_model: str = "muse-spark-1.3"    # resolves spoken references
    escalate_model: str = "muse-wonder-1.0"  # retry when Spark abstains (offline: speed ok)
    transcribe_model: str = "muse-voice-transcribe-1.0"
    sam_model: str = ""                      # SAM 3.1 id on the Model API: verify
    confidence_threshold: float = 0.7
    # camera / page tools (scripts/page_preview.py, sensing/hand.py)
    camera_index: int = 0
    paper: str = "letter"
    orientation: str = "landscape"
    page_rotation: int = 0


def load_settings() -> Settings:
    load_dotenv()
    env = os.getenv
    return Settings(
        api_key=env("META_API_KEY", ""),
        base_url=env("META_API_BASE_URL") or Settings.base_url,
        board_model=env("SEED_BOARD_MODEL", Settings.board_model),
        resolve_model=env("SEED_RESOLVE_MODEL", Settings.resolve_model),
        escalate_model=env("SEED_ESCALATE_MODEL", Settings.escalate_model),
        transcribe_model=env("SEED_TRANSCRIBE_MODEL", Settings.transcribe_model),
        sam_model=env("SEED_SAM_MODEL", ""),
        confidence_threshold=float(env("SEED_CONFIDENCE_THRESHOLD", "0.7")),
        camera_index=int(env("PAPEROS_CAMERA_INDEX", "0")),
        paper=env("PAPEROS_PAPER", "letter"),
        orientation=env("PAPEROS_ORIENTATION", "landscape"),
        page_rotation=int(env("PAPEROS_PAGE_ROTATION", "0")),
    )
