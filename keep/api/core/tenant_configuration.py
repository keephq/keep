import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from keep.api.core.config import config
from keep.api.core.db import get_tenants_configurations

# Optional: if your db module has a per-tenant getter, we’ll use it.
try:
    # You add this to keep.api.core.db when ready:
    # def get_tenant_configuration(tenant_id: str) -> dict | None: ...
    from keep.api.core.db import get_tenant_configuration  # type: ignore
except Exception:
    get_tenant_configuration = None  # type: ignore


class TenantConfiguration:
    """
    Process-local tenant configuration cache with:
    - periodic full reload (minutes)
    - optional per-tenant lazy-load on cache miss (if DB function exists)
    - thread safety
    - UTC timestamps

    Note: This cache is per-process. Multiple gunicorn workers = multiple caches.
    """

    _instance: Optional["TenantConfiguration"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_once()
                    cls._instance = inst
        return cls._instance

    def _init_once(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()

        self.reload_minutes: int = config(
            "TENANT_CONFIGURATION_RELOAD_MINUTES", default=5, cast=int
        )
        if self.reload_minutes < 1:
            self.logger.warning(
                "Invalid TENANT_CONFIGURATION_RELOAD_MINUTES=%s; using 5",
                self.reload_minutes,
            )
            self.reload_minutes = 5

        # Optional: cap reload interval if someone sets it to nonsense
        if self.reload_minutes > 1440:
            self.logger.warning(
                "TENANT_CONFIGURATION_RELOAD_MINUTES=%s is huge; capping at 1440",
                self.reload_minutes,
            )
            self.reload_minutes = 1440

        self.last_loaded_utc: datetime = datetime.min.replace(tzinfo=timezone.utc)
        self.configurations: Dict[str, Dict[str, Any]] = {}

        # Initial load (best effort)
        self._reload_all(force=True)

    def _reload_due(self) -> bool:
        return (datetime.now(timezone.utc) - self.last_loaded_utc) > timedelta(
            minutes=self.reload_minutes
        )

    def _reload_all(self, force: bool = False) -> None:
        """
        Reload all tenant configurations.
        Never replaces a valid cache with an empty result (unless cache empty and force=True).
        """
        with self._lock:
            if not force and not self._reload_due():
                return

            self.logger.debug("Loading tenant configurations from DB (full reload)")
            try:
                fresh = get_tenants_configurations() or {}
            except Exception:
                self.logger.exception("Failed to load tenant configurations from DB (full reload)")
                return

            # Don’t wipe a good cache if DB returns empty.
            if not fresh and self.configurations:
                self.logger.warning(
                    "Full reload returned 0 tenants; keeping existing cache"
                )
                self.last_loaded_utc = datetime.now(timezone.utc)
                return

            self.configurations = fresh
            self.last_loaded_utc = datetime.now(timezone.utc)

            self.logger.info(
                "Tenant configurations loaded",
                extra={"number_of_tenants": len(self.configurations)},
            )

    def _lazy_load_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Optional upgrade: load a single tenant configuration from DB if supported.
        If not supported, returns None.
        """
        if get_tenant_configuration is None:
            return None

        try:
            tenant_cfg = get_tenant_configuration(tenant_id)  # type: ignore[misc]
        except Exception:
            self.logger.exception(
                "Failed to lazy-load tenant configuration",
                extra={"tenant_id": tenant_id},
            )
            return None

        if not tenant_cfg:
            return None

        with self._lock:
            # Merge into cache without forcing a full reload
            self.configurations[tenant_id] = tenant_cfg

        return tenant_cfg

    def get_configuration(self, tenant_id: str, config_name: Optional[str] = None):
        """
        Return full tenant config dict or one config value.
        Raises HTTP 401 if tenant missing.
        """
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Tenant not found [id: empty]")

        # Periodic full reload (cheap control plane)
        self._reload_all(force=False)

        with self._lock:
            tenant_config = self.configurations.get(tenant_id)

        if tenant_config is None:
            # First: try optional per-tenant lazy load (fast path)
            tenant_config = self._lazy_load_tenant(tenant_id)

        if tenant_config is None:
            # Second: fallback to one forced full reload (slow path, but controlled)
            self.logger.debug(
                "Tenant %s not found; forcing full reload", tenant_id
            )
            self._reload_all(force=True)
            with self._lock:
                tenant_config = self.configurations.get(tenant_id)

        if tenant_config is None:
            self.logger.warning("Tenant not found", extra={"tenant_id": tenant_id})
            raise HTTPException(
                status_code=401, detail=f"Tenant not found [id: {tenant_id}]"
            )

        if config_name is None:
            return tenant_config

        return tenant_config.get(config_name)