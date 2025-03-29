import json
import logging
import re

import keep.api.core.db as db
from keep.api.core.config import config
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


def provision_deduplication_rules(deduplication_rules: dict[str, any], tenant_id: str):
    """
    Provisions deduplication rules for a given tenant.

    Args:
        deduplication_rules (dict[str, any]): A dictionary where the keys are rule names and the values are
        DeduplicationRuleRequestDto objects.
        tenant_id (str): The ID of the tenant for which deduplication rules are being provisioned.
    """
    enrich_with_providers_info(deduplication_rules, tenant_id)

    all_deduplication_rules_from_db = db.get_all_deduplication_rules(tenant_id)
    provisioned_deduplication_rules = [
        rule for rule in all_deduplication_rules_from_db if rule.is_provisioned
    ]
    provisioned_deduplication_rules_from_db_dict = {
        rule.name: rule for rule in provisioned_deduplication_rules
    }
    actor = "system"

    # delete rules that are not in the env
    for provisioned_deduplication_rule in provisioned_deduplication_rules:
        if str(provisioned_deduplication_rule.name) not in deduplication_rules:
            logger.info(
                "Deduplication rule with name '%s' is not in the env, deleting from DB",
                provisioned_deduplication_rule.name,
            )
            db.delete_deduplication_rule(
                rule_id=str(provisioned_deduplication_rule.id), tenant_id=tenant_id
            )

    for deduplication_rule_to_provision in deduplication_rules.values():
        if (
            deduplication_rule_to_provision.get("name")
            in provisioned_deduplication_rules_from_db_dict
        ):
            logger.info(
                "Deduplication rule with name '%s' already exists, updating in DB",
                deduplication_rule_to_provision.get("name"),
            )
            db.update_deduplication_rule(
                tenant_id=tenant_id,
                rule_id=str(
                    provisioned_deduplication_rules_from_db_dict.get(
                        deduplication_rule_to_provision.get("name")
                    ).id
                ),
                name=deduplication_rule_to_provision.get("name"),
                description=deduplication_rule_to_provision.get("description"),
                provider_id=deduplication_rule_to_provision.get("provider_id"),
                provider_type=deduplication_rule_to_provision.get("provider_type"),
                last_updated_by=actor,
                enabled=True,
                fingerprint_fields=deduplication_rule_to_provision.get(
                    "fingerprint_fields"
                ),
                full_deduplication=deduplication_rule_to_provision.get(
                    "full_deduplication"
                ),
                ignore_fields=deduplication_rule_to_provision.get("ignore_fields")
                or [],
                priority=0,
            )
            continue

        logger.info(
            "Deduplication rule with name '%s' does not exist, creating in DB",
            deduplication_rule_to_provision.get("name"),
        )
        db.create_deduplication_rule(
            tenant_id=tenant_id,
            name=deduplication_rule_to_provision.get("name"),
            description=deduplication_rule_to_provision.get("description"),
            provider_id=deduplication_rule_to_provision.get("provider_id"),
            provider_type=deduplication_rule_to_provision.get("provider_type"),
            created_by=actor,
            enabled=True,
            fingerprint_fields=deduplication_rule_to_provision.get(
                "fingerprint_fields"
            ),
            full_deduplication=deduplication_rule_to_provision.get(
                "full_deduplication"
            ),
            ignore_fields=deduplication_rule_to_provision.get("ignore_fields") or [],
            priority=0,
            is_provisioned=True,
        )


def provision_deduplication_rules_from_env(tenant_id: str):
    """
    Provisions deduplication rules from environment variables for a given tenant.
    This function reads deduplication rules from environment variables, validates them,
    and then provisions them into the database. It handles the following:
    - Deletes deduplication rules from the database that are not present in the environment variables.
    - Updates existing deduplication rules in the database if they are present in the environment variables.
    - Creates new deduplication rules in the database if they are not already present.
    Args:
        tenant_id (str): The ID of the tenant for which deduplication rules are being provisioned.
    Raises:
        ValueError: If the deduplication rules from the environment variables are invalid.
    """

    deduplication_rules_from_env_dict = get_deduplication_rules_to_provision()

    if not deduplication_rules_from_env_dict:
        logger.info("No deduplication rules found in env. Nothing to provision.")
        return

    provision_deduplication_rules(deduplication_rules_from_env_dict, tenant_id)


def enrich_with_providers_info(deduplication_rules: dict[str, any], tenant_id: str):
    """
    Enriches passed deduplication rules with provider ID and type information.

    Args:
        deduplication_rules (dict[str, any]): A list of deduplication rules to be enriched.
        tenant_id (str): The ID of the tenant for which deduplication rules are being provisioned.
    """

    installed_providers = ProvidersFactory.get_installed_providers(tenant_id)
    installed_providers_dict = {
        provider.details.get("name"): provider for provider in installed_providers
    }

    for rule_name, rule in deduplication_rules.items():
        logger.info(f"Enriching deduplication rule: {rule_name}")
        provider = installed_providers_dict.get(rule.get("provider_name"))
        rule["provider_id"] = provider.id
        rule["provider_type"] = provider.type


def get_deduplication_rules_to_provision() -> dict[str, dict]:
    """
    Reads deduplication rules from an environment variable and returns them as a dictionary.
    The function checks if the environment variable `KEEP_DEDUPLICATION_RULES` contains a path to a JSON file
    or a JSON string. If it is a path, it reads the file and parses the JSON content. If it is a JSON string,
    it parses the string directly.
    Returns:
        dict[str, DeduplicationRuleRequestDto]: A dictionary where the keys are rule names and the values are
        DeduplicationRuleRequestDto objects.
    Raises:
        Exception: If there is an error parsing the JSON content from the file or the environment variable.
    """

    env_var_key = "KEEP_PROVIDERS"
    deduplication_rules_from_env_var = config(key=env_var_key, default=None)

    if not deduplication_rules_from_env_var:
        return None

    # check if env var is absolute or relative path to a deduplication rules json file
    if re.compile(r"^(\/|\.\/|\.\.\/).*\.json$").match(
        deduplication_rules_from_env_var
    ):
        with open(
            file=deduplication_rules_from_env_var, mode="r", encoding="utf8"
        ) as file:
            try:
                deduplication_rules_from_env_json: dict = json.loads(file.read())
            except json.JSONDecodeError as e:
                raise Exception(
                    f"Error parsing deduplication rules from file {deduplication_rules_from_env_var}: {e}"
                ) from e
    else:
        try:
            deduplication_rules_from_env_json = json.loads(
                deduplication_rules_from_env_var
            )
        except json.JSONDecodeError as e:
            raise Exception(
                f"Error parsing deduplication rules from env var {env_var_key}: {e}"
            ) from e

    deduplication_rules_dict: dict[str, dict] = {}

    for provider_name, provider_config in deduplication_rules_from_env_json.items():
        for rule_name, rule_config in provider_config.get(
            "deduplication_rules", {}
        ).items():
            rule_config["name"] = rule_name
            rule_config["provider_name"] = provider_name
            rule_config["provider_type"] = provider_config.get("type")
            deduplication_rules_dict[rule_name] = rule_config

    if not deduplication_rules_dict:
        return None

    return deduplication_rules_dict
