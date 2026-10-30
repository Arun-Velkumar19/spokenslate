"""Settings from environment / .env.

Variables are SPOKENSLATE_*. The pre-rename names (SEED_* for models, PAPEROS_* for the
camera tools) are still read as fallbacks so an existing .env keeps working.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://api.meta.ai/v1"
    # Models (playground-verified Oct 27: muse-spark-1.3 resolved 10/10 references)
    board_model: str = "muse-spark-1.3"      # reads the board each keyframe
    resolve_model: str = "muse-spark-1.3"    # resolves spoken references
    escalate_model: str = "muse-wonder-1.0"  # retry when Spark abstains (offline: speed ok)
    whisper_model: str = "small.en"           # local faster-whisper (word timestamps)
    sam_model: str = "sam-3.1"               # lecturer mask (verified Oct 30); "" = off
    confidence_threshold: float = 0.7
    # camera / page tools (scripts/page_preview.py, sensing/hand.py)
    camera_index: int = 0
    paper: str = "letter"
    orientation: str = "landscape"
    page_rotation: int = 0


def _env(name: str, old_prefix: str, default: str) -> str:
    """SPOKENSLATE_<name>, else <old_prefix>_<name>, else default. Empty counts as unset."""
    return os.getenv(f"SPOKENSLATE_{name}") or os.getenv(f"{old_prefix}_{name}") or default


def load_settings() -> Settings:
    load_dotenv()
    s = Settings
    return Settings(
        api_key=os.getenv("META_API_KEY", ""),
        base_url=os.getenv("META_API_BASE_URL") or s.base_url,
        board_model=_env("BOARD_MODEL", "SEED", s.board_model),
        resolve_model=_env("RESOLVE_MODEL", "SEED", s.resolve_model),
        escalate_model=_env("ESCALATE_MODEL", "SEED", s.escalate_model),
        whisper_model=os.getenv("SPOKENSLATE_WHISPER_MODEL") or s.whisper_model,
        sam_model=_env("SAM_MODEL", "SEED", s.sam_model),
        confidence_threshold=float(_env("CONFIDENCE_THRESHOLD", "SEED", "0.7")),
        camera_index=int(_env("CAMERA_INDEX", "PAPEROS", "0")),
        paper=_env("PAPER", "PAPEROS", s.paper),
        orientation=_env("ORIENTATION", "PAPEROS", s.orientation),
        page_rotation=int(_env("PAGE_ROTATION", "PAPEROS", "0")),
    )
