import copy
import hashlib
import json
import logging

import celpy

from keep.api.core.config import config
from keep.api.core.db import (
    get_all_dedup_ratio,
    get_all_deduplication_rules,
    get_last_alert_hash_by_fingerprint,
    get_provider_distribution,
)
from keep.api.models.alert import AlertDto, DeduplicationRuleDto
from keep.providers.providers_factory import ProvidersFactory


# decide whether this should be a singleton so that we can keep the filters in memory
class AlertDeduplicator:
    # this fields will be removed from the alert before hashing
    # TODO: make this configurable
    DEFAULT_FIELDS = ["lastReceived"]

    def __init__(self, tenant_id):
        self.filters = get_all_deduplication_rules(tenant_id)
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.provider_distribution_enabled = config(
            "PROVIDER_DISTRIBUTION_ENABLED", cast=bool, default=True
        )

    def is_deduplicated(self, alert: AlertDto) -> bool:
        # Apply all deduplication filters
        for filt in self.filters:
            alert = self._apply_deduplication_filter(filt, alert)

        # Remove default fields
        for field in AlertDeduplicator.DEFAULT_FIELDS:
            alert = self._remove_field(field, alert)

        # Calculate the hash
        alert_hash = hashlib.sha256(
            json.dumps(alert.dict(), default=str).encode()
        ).hexdigest()

        # Check if the hash is already in the database
        last_alert_hash_by_fingerprint = get_last_alert_hash_by_fingerprint(
            self.tenant_id, alert.fingerprint
        )
        alert_deduplicate = (
            True
            if last_alert_hash_by_fingerprint
            and last_alert_hash_by_fingerprint == alert_hash
            else False
        )
        if alert_deduplicate:
            self.logger.info(f"Alert {alert.id} is deduplicated {alert.source}")

        return alert_hash, alert_deduplicate

    def _run_matcher(self, matcher, alert: AlertDto) -> bool:
        # run the CEL matcher
        env = celpy.Environment()
        ast = env.compile(matcher)
        prgm = env.program(ast)
        activation = celpy.json_to_cel(
            json.loads(json.dumps(alert.dict(), default=str))
        )
        try:
            r = prgm.evaluate(activation)
        except celpy.evaluation.CELEvalError as e:
            # this is ok, it means that the subrule is not relevant for this event
            if "no such member" in str(e):
                return False
            # unknown
            raise
        return True if r else False

    def _apply_deduplication_filter(self, filt, alert: AlertDto) -> AlertDto:
        # check if the matcher applies
        filter_apply = self._run_matcher(filt.matcher_cel, alert)
        if not filter_apply:
            self.logger.debug(f"Filter {filt.id} did not match")
            return alert

        # remove the fields
        for field in filt.fields:
            alert = self._remove_field(field, alert)

        return alert

    def _remove_field(self, field, alert: AlertDto) -> AlertDto:
        # remove the field from the alert
        alert = copy.deepcopy(alert)
        field_parts = field.split(".")
        # if its not a nested field
        if len(field_parts) == 1:
            try:
                delattr(alert, field)
            except AttributeError:
                self.logger.warning("Failed to delete attribute {field} from alert")
                pass
        # if its a nested field, copy the dictionaty and remove the field
        # this is for cases such as labels/tags
        else:
            alert_attr = field_parts[0]
            d = copy.deepcopy(getattr(alert, alert_attr))
            for part in field_parts[1:-1]:
                d = d[part]
            del d[field_parts[-1]]
            setattr(alert, field_parts[0], d)
        return alert

    def get_deduplications(self) -> list[DeduplicationRuleDto]:
        installed_providers = ProvidersFactory.get_installed_providers(self.tenant_id)
        # filter out the providers that are not "alert" in tags
        installed_providers = [
            provider for provider in installed_providers if "alert" in provider.tags
        ]
        linked_providers = ProvidersFactory.get_linked_providers(self.tenant_id)
        providers = [*installed_providers, *linked_providers]

        default_deduplications = ProvidersFactory.get_default_deduplications()
        default_deduplications_dict = {
            dd.provider_type: dd for dd in default_deduplications
        }

        custom_deduplications = get_all_deduplication_rules(self.tenant_id)
        custom_deduplications_dict = {
            filt.provider_id: filt for filt in custom_deduplications
        }

        final_deduplications = []
        # if provider doesn't have custom deduplication, use the default one
        for provider in providers:
            if provider.id not in custom_deduplications_dict:
                if provider.type not in default_deduplications_dict:
                    self.logger.warning(
                        f"Provider {provider.type} does not have a default deduplication"
                    )
                    continue

                # copy the default deduplication and set the provider id
                default_deduplication = copy.deepcopy(
                    default_deduplications_dict[provider.type]
                )
                if provider.id:
                    default_deduplication.description = (
                        f"{default_deduplication.description} - {provider.id}"
                    )
                    default_deduplication.provider_id = provider.id

                final_deduplications.append(default_deduplication)
            else:
                final_deduplications.append(custom_deduplications_dict[provider.id])

        dedup_ratio = get_all_dedup_ratio(self.tenant_id)

        result = []
        for dedup in final_deduplications:
            dedup.ingested = dedup_ratio.get(
                (dedup.provider_id, dedup.provider_type), {}
            ).get("num_alerts", 0.0)
            dedup.dedup_ratio = dedup_ratio.get(
                (dedup.provider_id, dedup.provider_type), {}
            ).get("ratio", 0.0)
            result.append(dedup)

        # todo: add dedicated table
        if self.provider_distribution_enabled:
            providers_distribution = get_provider_distribution(self.tenant_id)
            for dedup in result:
                for pd in providers_distribution:
                    if pd == f"{dedup.provider_id}_{dedup.provider_type}":
                        distribution = providers_distribution[pd].get(
                            "alert_last_24_hours"
                        )
                        dedup.distribution = distribution
                        break

        return result
