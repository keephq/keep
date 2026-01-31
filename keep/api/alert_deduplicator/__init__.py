"""
Deduplication provisioning module.

This package handles loading, validating, enriching, and provisioning
deduplication rules from environment configuration into persistent storage.

Public API:
- provision_deduplication_rules_from_env
- provision_deduplication_rules
"""

from .provisioning import (
    provision_deduplication_rules,
    provision_deduplication_rules_from_env,
)

from .loader import (
    get_deduplication_rules_to_provision,
)

from .enrichment import (
    enrich_with_providers_info,
)

__all__ = [
    "provision_deduplication_rules",
    "provision_deduplication_rules_from_env",
    "get_deduplication_rules_to_provision",
    "enrich_with_providers_info",
]