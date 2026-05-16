from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover
    _load_dotenv = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KernelSettings:
    openai_api_key: str
    openai_model: str
    log_level: str

    @property
    def api_key_configured(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_kernel_settings() -> KernelSettings:
    """Load and validate kernel settings from environment variables."""
    if _load_dotenv is not None:
        _load_dotenv(override=False)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5"
    log_level = os.getenv("KERNEL_LOG_LEVEL", "INFO").strip().upper()

    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not set; LLM calls will fail at runtime. "
            "Local plugins (PriorityTriage, ExecutiveSummary, AuditCompliance) "
            "will still work without it."
        )

    return KernelSettings(
        openai_api_key=api_key,
        openai_model=model,
        log_level=log_level,
    )
