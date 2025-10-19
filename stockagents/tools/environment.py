"""Environment helpers shared by tool implementations."""

from __future__ import annotations

import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def load_local_env(filename: str = ".env") -> None:
    """Load environment variables from ``filename`` relative to the project root."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / filename
    if not env_path.is_file():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()
    except OSError:
        LOGGER.warning("Failed to read %s", env_path)
