"""
Application configuration loader.

Loads config from:
1) .env.{ENVIRONMENT} (if ENVIRONMENT is set and file exists)
2) .env (if exists)
3) environment variables only (fallback)

Environment variables always take precedence (Starlette behavior).
"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Optional

try:
    from starlette.config import Config
except ImportError as e:
    raise ImportError("starlette is required for configuration") from e


logger = logging.getLogger(__name__)

# Path layout assumption: <project_root>/app/.../config.py
ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
BASE_DIR: pathlib.Path = ROOT.parent

_config: Optional[Config] = None


def load_config() -> Config:
    env_name = (os.getenv("ENVIRONMENT") or "").strip()
    candidates = []

    if env_name:
        candidates.append(BASE_DIR / f".env.{env_name}")
    candidates.append(BASE_DIR / ".env")

    for path in candidates:
        if not path.exists():
            continue

        try:
            cfg = Config(str(path))
            logger.info("Loaded configuration from %s", path)
            return cfg
        except (PermissionError, IsADirectoryError) as e:
            logger.error("Cannot read config file %s: %s", path, e)
            raise
        except Exception as e:
            logger.error("Failed to load config file %s: %s", path, e, exc_info=True)
            raise

    # Fallback
    logger.warning(
        "No .env file found (checked: %s). Falling back to environment variables only.",
        ", ".join(str(p) for p in candidates),
    )
    return Config()


def get_config(reload: bool = False) -> Config:
    global _config
    if _config is None or reload:
        _config = load_config()
    return _config


# Backward compatibility (old imports keep working)
config: Config = get_config()