"""
Standalone conftest — stubs out all Keep internal deps so our provider
tests can run without the full Keep stack installed.

Usage:
    pytest tests/test_snmp_provider.py tests/test_solarwinds_provider.py \
        -v --noconftest -p conftest_standalone

Or just copy this to conftest.py in the repo root (overrides the real one).
"""

import sys
import types
from enum import Enum
from unittest.mock import MagicMock

# Pre-import real packages so they're in sys.modules before we add stubs
# This ensures keep.providers.snmp_provider etc. resolve correctly
import keep  # noqa
import keep.providers  # noqa

# ---------------------------------------------------------------------------
# 1.  Minimal AlertSeverity / AlertStatus / AlertDto stubs
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"
    LOW = "low"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    PENDING = "pending"
    SUPPRESSED = "suppressed"


class AlertDto:
    """Minimal AlertDto — stores kwargs as attributes, allows extra fields."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # ensure required-ish fields exist
        self.source = kwargs.get("source", [])
        self.severity = kwargs.get("severity", AlertSeverity.INFO)
        self.status = kwargs.get("status", AlertStatus.FIRING)
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description", "")
        self.fingerprint = kwargs.get("fingerprint", "")

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------------
# 2.  Minimal ProviderConfig stub
# ---------------------------------------------------------------------------

class ProviderConfig:
    def __init__(self, *args, **kwargs):
        self.authentication = kwargs.get("authentication", {})
        self.name = kwargs.get("name", "stub")
        self.description = kwargs.get("description", "")


class ProviderScope:
    def __init__(self, *args, **kwargs):
        pass


class ProviderMethod:
    def __init__(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# 3.  Minimal ContextManager stub
# ---------------------------------------------------------------------------

class ContextManager:
    def __init__(self, *args, **kwargs):
        pass

    def get_full_context(self, *a, **k):
        return {}

    def set_context(self, *a, **k):
        pass

    def get_context(self, *a, **k):
        return None


# ---------------------------------------------------------------------------
# 4.  Minimal BaseProvider stub
# ---------------------------------------------------------------------------

class BaseProvider:
    PROVIDER_DISPLAY_NAME = ""
    PROVIDER_CATEGORY = []
    PROVIDER_TAGS = []
    FINGERPRINT_FIELDS = []
    PROVIDER_DESCRIPTION = ""
    WEBHOOK_DESCRIPTION = ""
    WEBHOOK_TEMPLATE = ""

    def __init__(self, context_manager=None, provider_id="stub", config=None):
        self.context_manager = context_manager or ContextManager()
        self.provider_id = provider_id
        self.config = config or ProviderConfig()
        self.logger = __import__("logging").getLogger(self.__class__.__name__)

    @classmethod
    def simulate_alert(cls):
        """Default: import sibling alerts_mock and return first alert payload."""
        import importlib, os
        module_name = cls.__module__  # e.g. keep.providers.snmp_provider.snmp_provider
        parts = module_name.split(".")
        # e.g. keep.providers.snmp_provider.alerts_mock
        mock_module_name = ".".join(parts[:-1] + ["alerts_mock"])
        try:
            mod = importlib.import_module(mock_module_name)
            alerts = getattr(mod, "ALERTS", {})
            if alerts:
                first = next(iter(alerts.values()))
                return first.get("payload", first)
        except Exception:
            pass
        return {}

    def validate_scopes(self):
        return {}

    def dispose(self):
        pass

    def get_alerts(self):
        return []


# ---------------------------------------------------------------------------
# 5.  Wire everything into sys.modules BEFORE any provider import
# ---------------------------------------------------------------------------

def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


# keep.api.models.alert
alert_mod = _make_module(
    "keep.api.models.alert",
    AlertDto=AlertDto,
    AlertSeverity=AlertSeverity,
    AlertStatus=AlertStatus,
)

# keep.api.models.severity_base
severity_base_mod = _make_module(
    "keep.api.models.severity_base",
    SeverityBaseInterface=object,
)

# keep.providers.models.provider_config
pconfig_mod = _make_module(
    "keep.providers.models.provider_config",
    ProviderConfig=ProviderConfig,
    ProviderScope=ProviderScope,
)

# keep.providers.models.provider_method
pmethod_mod = _make_module(
    "keep.providers.models.provider_method",
    ProviderMethod=ProviderMethod,
)

# keep.providers.base.base_provider
base_mod = _make_module(
    "keep.providers.base.base_provider",
    BaseProvider=BaseProvider,
)

# keep.contextmanager.contextmanager
ctx_mod = _make_module(
    "keep.contextmanager.contextmanager",
    ContextManager=ContextManager,
)

# Stub out everything else Keep might pull in
_stub_modules = [
    "keep",
    "keep.api",
    "keep.api.models",
    "keep.api.models.db",
    "keep.api.models.db.topology",
    "keep.api.models.incident",
    "keep.api.models.action_type",
    "keep.api.core",
    "keep.api.core.db",
    "keep.api.core.config",
    "keep.api.bl",
    "keep.api.bl.enrichments_bl",
    "keep.api.logging",
    "keep.api.utils",
    "keep.api.utils.enrichment_helpers",
    "keep.providers",
    "keep.providers.models",
    "keep.providers.base",
    "keep.contextmanager",
]

for mod_name in _stub_modules:
    if mod_name not in sys.modules:
        m = _make_module(mod_name)
        sys.modules[mod_name] = m

# Override with real stubs AFTER setting generic stubs
# (but don't touch real packages keep / keep.providers — they exist on disk)

# Override with real stubs
sys.modules["keep.api.models.alert"] = alert_mod
sys.modules["keep.api.models.severity_base"] = severity_base_mod
sys.modules["keep.providers.models.provider_config"] = pconfig_mod
sys.modules["keep.providers.models.provider_method"] = pmethod_mod
sys.modules["keep.providers.base.base_provider"] = base_mod
sys.modules["keep.contextmanager.contextmanager"] = ctx_mod

# Stub third-party deps that might not be installed
for _dep in [
    "opentelemetry.trace", "opentelemetry", "dateutil", "dateutil.parser",
    "pympler", "pympler.asizeof", "json5", "click", "starlette",
    "starlette.config", "fastapi", "sqlmodel", "sqlalchemy",
    "opentelemetry.sdk", "opentelemetry.api",
]:
    if _dep not in sys.modules:
        sys.modules[_dep] = MagicMock()
