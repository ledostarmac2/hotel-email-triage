from __future__ import annotations

from pathlib import Path

from .models import KycStatus
from .service import KycService


def check_due_reminder(db_path: Path | None = None) -> KycStatus:
    """Return current KYC reminder state, creating a due event when needed."""
    return KycService(db_path).status()
