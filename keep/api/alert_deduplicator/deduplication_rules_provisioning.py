import json
import logging
import re


from keep.api.core.config import config
import keep.api.core.db as db
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)

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

    validate_deduplication_rules(
        tenant_id, list(deduplication_rules_from_env_dict.values())
    )

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
        if (
            str(provisioned_deduplication_rule.name)
            not in deduplication_rules_from_env_dict
        ):
            logger.info(
                "Deduplication rule with name '%s' is not in the env, deleting from DB",
                provisioned_deduplication_rule.name,
            )
            db.delete_deduplication_rule(rule_id=str(provisioned_deduplication_rule.id), tenant_id=tenant_id)

    for deduplication_rule_to_provision in deduplication_rules_from_env_dict.values():
        # check if the rule already exists and needs to be overwritten
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
                fingerprint_fields=deduplication_rule_to_provision.get("fingerprint_fields"),
                full_deduplication=deduplication_rule_to_provision.get("full_deduplication"),
                ignore_fields=deduplication_rule_to_provision.get("ignore_fields") or [],
                priority=0,
            )
            continue

        # create the rule
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
            fingerprint_fields=deduplication_rule_to_provision.get("fingerprint_fields"),
            full_deduplication=deduplication_rule_to_provision.get("full_deduplication"),
            ignore_fields=deduplication_rule_to_provision.get("ignore_fields") or [],
            priority=0,
            is_provisioned=True,
        )


def validate_deduplication_rules(
    tenant_id: str, deduplication_rules: list[dict]
):
    """
    Validates deduplication rules for a given tenant.
    This function performs the following validations:
    1. Ensures that all deduplication rule names are unique.
    2. Checks that each rule points to an existing provider.
    Args:
        tenant_id (str): The ID of the tenant.
        deduplication_rules (list[dict]): A list of deduplication rules, where each rule is represented as a dictionary.
    Raises:
        ValueError: If any rule points to a non-existing provider.
    Returns:
        None
    """

    logger.info("Validating deduplication rules")

    installed_providers = ProvidersFactory.get_installed_providers(tenant_id)
    linked_providers = ProvidersFactory.get_linked_providers(tenant_id)
    errors: dict[str, list[str]] = {}

    installed_providers_dict = {
        f"{p.type}_{p.id}": p for p in installed_providers + linked_providers
    }

    for rule in deduplication_rules:
        rule_id = rule.get("id")
        rule_provider_type = rule.get("provider_type")
        rule_provider_id = rule.get("provider_id")
        rule_name = rule.get("name")
        provider_key = f"{rule_provider_type}_{rule_provider_id}"
        
        if provider_key not in installed_providers_dict:
            errors[rule_id] = [] if rule_id not in errors else errors[rule_id]
            errors[rule_id].append(
                f"Deduplication rule with name '{rule_name}' points to not existing provider of type '{rule_provider_type}' with id '{rule_provider_id}'"
            )

    if len(errors) > 0:
        flattened_errors = [error for sublist in errors.values() for error in sublist]
        raise ValueError(" ".join(flattened_errors))

    logger.info("Deduplication rules are valid")


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

    env_var_key = "KEEP_DEDUPLICATION_RULES"
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
                deduplication_rules_from_env_json = json.loads(file.read())
            except json.JSONDecodeError as e:
                raise Exception(
                    f"Error parsing deduplication rules from file {deduplication_rules_from_env_var}: {e}"
                ) from e
    else:
        try:
            deduplication_rules_from_env_json = json.loads(deduplication_rules_from_env_var)
        except json.JSONDecodeError as e:
            raise Exception(
                f"Error parsing deduplication rules from env var {env_var_key}: {e}"
            ) from e

    # enrich the rules with the properties that are not present in the JSON
    for rule in deduplication_rules_from_env_json:
        rule["is_provisioned"] = True

    return {
        rule["name"]: rule
        for rule in deduplication_rules_from_env_json
    }
