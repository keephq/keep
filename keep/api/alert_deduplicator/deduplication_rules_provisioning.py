import json
import logging
import os
import re
from copy import deepcopy
from typing import Any, Mapping

import keep.api.core.db as db
from keep.api.core.config import config
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)

ENV_VAR_DEDUP_RULES = "KEEP_DEDUPLICATION_RULES"

_PATH_RE = re.compile(r"^(\/|\.\/|\.\.\/).*\.json$", re.IGNORECASE)


def provision_deduplication_rules(deduplication_rules: Mapping[str, dict[str, Any]], tenant_id: str) -> None:
    """
    Provisions deduplication rules for a given tenant.

    Args:
        deduplication_rules: dict mapping rule_name -> rule config dict
        tenant_id: tenant id
    """
    # Work on a copy so callers don't get surprise mutations.
    rules = deepcopy(dict(deduplication_rules))

    # Enrich + validate EVERYTHING before we touch the DB.
    rules = enrich_with_providers_info(rules, tenant_id)

    all_rules_from_db = db.get_all_deduplication_rules(tenant_id)
    provisioned_rules = [r for r in all_rules_from_db if r.is_provisioned]
    provisioned_by_name = {r.name: r for r in provisioned_rules}

    actor = "system"

    # Compute changes first (fail-fast strategy).
    desired_names = set(rules.keys())
    existing_names = set(provisioned_by_name.keys())

    to_delete = existing_names - desired_names
    to_upsert = desired_names  # update if exists else create

    # If your db layer supports transactions, use it.
    # If not, this still avoids failing after deletes by doing validation/enrichment first.
    try:
        # Delete rules not in env
        for name in to_delete:
            rule_obj = provisioned_by_name[name]
            logger.info("Deduplication rule '%s' missing from env, deleting from DB", name)
            db.delete_deduplication_rule(rule_id=str(rule_obj.id), tenant_id=tenant_id)

        # Upsert desired rules
        for name in to_upsert:
            payload = rules[name]
            provider_type = payload.get("provider_type")
            if not provider_type:
                raise ValueError(f"Rule '{name}' is missing provider_type after enrichment")

            if name in provisioned_by_name:
                logger.info("Deduplication rule '%s' exists, updating in DB", name)
                db.update_deduplication_rule(
                    tenant_id=tenant_id,
                    rule_id=str(provisioned_by_name[name].id),
                    name=name,
                    description=payload.get("description", ""),
                    provider_id=payload.get("provider_id"),
                    provider_type=provider_type,
                    last_updated_by=actor,
                    enabled=True,
                    fingerprint_fields=payload.get("fingerprint_fields", []) or [],
                    full_deduplication=payload.get("full_deduplication", False),
                    ignore_fields=payload.get("ignore_fields") or [],
                    priority=int(payload.get("priority", 0) or 0),
                )
            else:
                logger.info("Deduplication rule '%s' does not exist, creating in DB", name)
                db.create_deduplication_rule(
                    tenant_id=tenant_id,
                    name=name,
                    description=payload.get("description", ""),
                    provider_id=payload.get("provider_id"),
                    provider_type=provider_type,
                    created_by=actor,
                    enabled=True,
                    fingerprint_fields=payload.get("fingerprint_fields", []) or [],
                    full_deduplication=payload.get("full_deduplication", False),
                    ignore_fields=payload.get("ignore_fields") or [],
                    priority=int(payload.get("priority", 0) or 0),
                    is_provisioned=True,
                )

    except Exception:
        logger.exception("Failed provisioning deduplication rules for tenant_id=%s", tenant_id)
        raise


def provision_deduplication_rules_from_env(tenant_id: str) -> None:
    rules = get_deduplication_rules_to_provision()

    if not rules:
        logger.info("No deduplication rules found in env. Nothing to provision.")
        return

    provision_deduplication_rules(rules, tenant_id)


def enrich_with_providers_info(deduplication_rules: dict[str, dict[str, Any]], tenant_id: str) -> dict[str, dict[str, Any]]:
    """
    Returns a NEW dict with provider_id/provider_type filled from installed providers.
    Raises ValueError if a referenced provider_name is not installed.
    """
    installed = ProvidersFactory.get_installed_providers(tenant_id)
    installed_by_name = {p.details.get("name"): p for p in installed}

    enriched: dict[str, dict[str, Any]] = {}

    for rule_name, rule in deduplication_rules.items():
        provider_name = rule.get("provider_name")
        if not provider_name:
            raise ValueError(f"Rule '{rule_name}' missing provider_name")

        provider = installed_by_name.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not installed for rule '{rule_name}'")

        r = dict(rule)  # shallow copy is enough after deepcopy upstream
        r["provider_id"] = provider.id
        # Single source of truth: provider.type from installed provider
        r["provider_type"] = provider.type
        enriched[rule_name] = r

    return enriched


def get_deduplication_rules_to_provision() -> dict[str, dict[str, Any]] | None:
    """
    Reads deduplication rules from ENV_VAR_DEDUP_RULES.
    Value can be:
      - a JSON string
      - a relative/absolute path to a .json file
    Returns dict: rule_name -> rule_config
    """
    raw = config(key=ENV_VAR_DEDUP_RULES, default=None)
    if not raw:
        return None

    raw = str(raw).strip()
    if not raw:
        return None

    # Load JSON either from file path or from string
    if _PATH_RE.match(raw):
        if not os.path.exists(raw):
            raise FileNotFoundError(f"Deduplication rules file not found: {raw}")
        with open(raw, "r", encoding="utf8") as f:
            deduplication_rules_from_env_json = json.loads(f.read())
    else:
        deduplication_rules_from_env_json = json.loads(raw)

    deduplication_rules_dict: dict[str, dict[str, Any]] = {}

    for provider_name, provider_config in (deduplication_rules_from_env_json or {}).items():
        rules = (provider_config or {}).get("deduplication_rules", {}) or {}
        for rule_name, rule_config in rules.items():
            if rule_name in deduplication_rules_dict:
                raise ValueError(
                    f"Duplicate deduplication rule name '{rule_name}' across providers "
                    f"(latest provider: '{provider_name}')"
                )

            rc = dict(rule_config or {})
            rc["name"] = rule_name
            rc["provider_name"] = provider_name
            # Don't set provider_type here. Enrichment will set it from installed provider metadata.
            deduplication_rules_dict[rule_name] = rc

    return deduplication_rules_dict or None