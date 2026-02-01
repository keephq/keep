"""
db_on_start.py

Master-process startup DB provisioning and migrations.

Key rules:
- This module is intended to run in the master/startup process only.
- Worker processes should not reuse this engine (not fork-safe).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import alembic.command
import alembic.config
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.core.config import config as app_config
from keep.api.core.db_utils import create_db_engine

# NOTE: Wildcard imports are used here to ensure model registration for table creation/migrations.
# pylint: disable=unused-wildcard-import,wildcard-import
from keep.api.models.db.alert import *
from keep.api.models.db.dashboard import *
from keep.api.models.db.extraction import *
from keep.api.models.db.mapping import *
from keep.api.models.db.preset import *
from keep.api.models.db.provider import *
from keep.api.models.db.rule import *
from keep.api.models.db.statistics import *
from keep.api.models.db.tenant import *
from keep.api.models.db.workflow import *
# pylint: enable=unused-wildcard-import,wildcard-import

from keep.identitymanager.rbac import Admin as AdminRole

logger = logging.getLogger(__name__)

engine = create_db_engine()

KEEP_FORCE_RESET_DEFAULT_PASSWORD: bool = app_config(
    "KEEP_FORCE_RESET_DEFAULT_PASSWORD", default="false", cast=bool
)
DEFAULT_USERNAME: str = app_config("KEEP_DEFAULT_USERNAME", default="keep")
DEFAULT_PASSWORD: str = app_config("KEEP_DEFAULT_PASSWORD", default="keep")

# PBKDF2 settings (stdlib, decent baseline)
PBKDF2_ITERATIONS: int = int(os.environ.get("KEEP_PBKDF2_ITERATIONS", "210000"))
PBKDF2_SALT_BYTES: int = int(os.environ.get("KEEP_PBKDF2_SALT_BYTES", "16"))


# ---------------------------
# Secure hashing (stdlib)
# ---------------------------

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode((txt + pad).encode("ascii"))


def hash_secret(secret: str) -> str:
    """
    Returns a self-describing hash string:
    pbkdf2_sha256$<iters>$<salt_b64>$<dk_b64>
    """
    if secret is None:
        raise ValueError("secret must not be None")
    salt = os.urandom(PBKDF2_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=32,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(dk)}"


def verify_secret(secret: str, stored: str) -> bool:
    """
    Verification helper for pbkdf2_sha256 hashes.
    (Not necessarily used here, but provides upgrade path and testing.)
    """
    try:
        scheme, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64d(salt_b64)
        expected = _b64d(dk_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), salt, iters, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ---------------------------
# Parsing + helpers
# ---------------------------

@dataclass(frozen=True)
class DefaultApiKeySpec:
    name: str
    role: str
    secret: str


def parse_default_api_key(raw: str) -> Optional[DefaultApiKeySpec]:
    """
    Expected format: name:role:secret
    Returns None if invalid.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    parts = [p.strip() for p in raw.split(":", 2)]
    if len(parts) != 3 or not all(parts):
        return None

    return DefaultApiKeySpec(name=parts[0], role=parts[1], secret=parts[2])


def _get_default_api_keys_from_env() -> list[DefaultApiKeySpec]:
    raw = os.environ.get("KEEP_DEFAULT_API_KEYS", "")
    if not raw.strip():
        return []

    specs: list[DefaultApiKeySpec] = []
    for item in raw.split(","):
        spec = parse_default_api_key(item)
        if not spec:
            logger.error(
                "Invalid default API key format: %r (expected name:role:secret). Skipping.",
                item.strip(),
            )
            continue
        specs.append(spec)
    return specs


# ---------------------------
# Provisioning
# ---------------------------

def try_create_single_tenant(tenant_id: str, create_default_user: bool = True) -> None:
    """
    Creates the single tenant and the default user if they don't exist.
    Provisions default API keys if configured.

    Raises on unexpected errors (startup should not pretend success).
    """
    # Import here to avoid import-time DB side effects elsewhere
    from keep.api.models.db.user import User  # pylint: disable=import-outside-toplevel

    default_api_keys = _get_default_api_keys_from_env()

    with Session(engine) as session:
        try:
            # --- Tenant ---
            tenant = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
            if not tenant:
                logger.info("Creating single tenant %s", tenant_id)
                session.add(Tenant(id=tenant_id, name="Single Tenant"))
            else:
                logger.info("Single tenant %s already exists", tenant_id)

            # --- Default user (correctly targeted) ---
            if create_default_user:
                default_user = session.exec(
                    select(User).where(User.username == DEFAULT_USERNAME)
                ).first()

                if not default_user:
                    logger.info("Creating default user %s", DEFAULT_USERNAME)
                    default_user = User(
                        username=DEFAULT_USERNAME,
                        password_hash=hash_secret(DEFAULT_PASSWORD),
                        role=AdminRole.get_name(),
                    )
                    session.add(default_user)
                elif KEEP_FORCE_RESET_DEFAULT_PASSWORD:
                    logger.warning(
                        "Forcing reset of default user password for %s", DEFAULT_USERNAME
                    )
                    default_user.password_hash = hash_secret(DEFAULT_PASSWORD)

            session.commit()

        except IntegrityError as e:
            # Usually "already exists" races; treat as non-fatal but DO rollback.
            session.rollback()
            logger.info(
                "IntegrityError during single-tenant provisioning (likely already provisioned): %s",
                e,
                exc_info=True,
            )
        except Exception as e:
            session.rollback()
            logger.exception("Fatal error provisioning single tenant %s", tenant_id)
            raise RuntimeError(
                f"Critical error during single tenant setup for tenant_id={tenant_id}"
            ) from e

        # --- Default API keys: process independently (avoid one failure blocking all) ---
        if not default_api_keys:
            return

        logger.info("Provisioning %d default API keys", len(default_api_keys))

        # External deps imported only if needed
        from keep.contextmanager.contextmanager import ContextManager  # pylint: disable=import-outside-toplevel
        from keep.secretmanager.secretmanagerfactory import SecretManagerFactory  # pylint: disable=import-outside-toplevel

        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)

        for spec in default_api_keys:
            with Session(engine) as key_session:
                try:
                    existing = key_session.exec(
                        select(TenantApiKey).where(
                            TenantApiKey.tenant_id == tenant_id,
                            TenantApiKey.reference_id == spec.name,
                        )
                    ).first()
                    if existing:
                        logger.info("API key %s already exists, skipping", spec.name)
                        continue

                    logger.info("Provisioning API key %s (role=%s)", spec.name, spec.role)

                    new_key = TenantApiKey(
                        tenant_id=tenant_id,
                        reference_id=spec.name,
                        key_hash=hash_secret(spec.secret),  # secure hash (not sha256)
                        is_system=True,
                        created_by="system",
                        role=spec.role,
                    )
                    key_session.add(new_key)
                    key_session.commit()

                except IntegrityError:
                    key_session.rollback()
                    logger.info(
                        "API key %s already exists (race). Skipping.",
                        spec.name,
                        exc_info=True,
                    )
                    continue
                except Exception as e:
                    key_session.rollback()
                    logger.exception("Failed provisioning API key %s", spec.name)
                    raise RuntimeError(f"Failed provisioning API key {spec.name}") from e

            # Secret write should not be inside DB transaction
            try:
                secret_manager.write_secret(
                    secret_name=f"{tenant_id}-{spec.name}",
                    secret_value=spec.secret,
                )
            except Exception:
                # Do not crash startup for secret-manager conflicts (e.g., already exists).
                logger.exception(
                    "Failed to write secret for API key %s (tenant %s). Continuing.",
                    spec.name,
                    tenant_id,
                )

        logger.info("Finished provisioning default API keys")


def migrate_db() -> None:
    """
    Run Alembic migrations to bring DB schema up-to-date.
    """
    if os.environ.get("SKIP_DB_CREATION", "false").lower() == "true":
        logger.info("Skipping migrations (SKIP_DB_CREATION=true)")
        return

    logger.info("Running migrations...")

    # Build paths robustly
    this_dir = Path(__file__).resolve().parent
    project_root = (this_dir / ".." / "..").resolve()
    alembic_ini = project_root / "alembic.ini"
    migrations_dir = (this_dir / ".." / "models" / "db" / "migrations").resolve()

    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    if not migrations_dir.exists():
        raise FileNotFoundError(f"migrations directory not found at {migrations_dir}")

    alembic_cfg = alembic.config.Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(migrations_dir))

    alembic.command.upgrade(alembic_cfg, "head")
    logger.info("Finished migrations")