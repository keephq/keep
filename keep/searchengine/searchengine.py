import enum
import logging

from keep.api.core.db import get_last_alerts
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.preset import PresetDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine


class SearchMode(enum.Enum):
    """The search mode for the search engine"""

    # use elastic to search alerts (for large tenants)
    ELASTIC = "elastic"
    # use internal search to search alerts (for small-medium tenants)
    INTERNAL = "internal"


class SearchEngine:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)
        self.rule_engine = RulesEngine(tenant_id=self.tenant_id)
        self.elastic_client = ElasticClient()
        self.rule_engine = RulesEngine(tenant_id=self.tenant_id)
        self.search_mode = (
            SearchMode.ELASTIC if self.elastic_client.enabled else SearchMode.INTERNAL
        )

    def search_preset_alerts(
        self, presets: list[PresetDto]
    ) -> dict[str, list[AlertDto]]:
        """Search for alerts based on a list of queries

        Args:
            presets (list[Preset]): The list of presets to search for

        Returns:
            dict[str, list[AlertDto]]: The list of alerts that match each query
        """
        self.logger.info("Searching alerts for presets")

        # if internal
        if self.search_mode == SearchMode.INTERNAL:
            # get the alerts
            alerts = get_last_alerts(tenant_id=self.tenant_id)

            # deduplicate fingerprints
            # shahar: this is backward compatibility for before we had milliseconds in the timestamp
            #          note that we want to keep the order of the alerts
            #          so we will keep the first alert and remove the rest
            dedup_alerts = []
            seen_fingerprints = set()
            for alert in alerts:
                if alert.fingerprint not in seen_fingerprints:
                    dedup_alerts.append(alert)
                    seen_fingerprints.add(alert.fingerprint)
                # this shouldn't appear with time (after migrating to milliseconds in timestamp)
                else:
                    self.logger.info(
                        "Skipping fingerprint", extra={"alert_id": alert.id}
                    )
            alerts = dedup_alerts
            # convert the alerts to DTO
            alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
            for preset in presets:
                filtered_alerts = self.rule_engine.filter_alerts(
                    alerts_dto, preset.cel_query
                )
                preset.alerts_count = len(filtered_alerts)
                # update noisy
                if preset.is_noisy:
                    firing_filtered_alerts = list(
                        filter(
                            lambda alert: alert.status == AlertStatus.FIRING.value
                            and not alert.deleted
                            and not alert.dismissed,
                            filtered_alerts,
                        )
                    )
                    # if there are firing alerts, then do noise
                    if firing_filtered_alerts:
                        self.logger.info("Noisy preset is noisy")
                        preset.should_do_noise_now = True
                    else:
                        self.logger.info("Noisy preset is not noisy")
                        preset.should_do_noise_now = False
                # else if one of the alerts are isNoisy
                elif not preset.static and any(
                    alert.isNoisy
                    and alert.status == AlertStatus.FIRING.value
                    and not alert.deleted
                    and not alert.dismissed
                    for alert in filtered_alerts
                ):
                    self.logger.info("Preset is noisy")
                    preset.should_do_noise_now = True

        # if elastic
        elif self.search_mode == SearchMode.ELASTIC:
            # get the alerts from elastic
            for preset in presets:
                query = self._create_raw_sql(
                    preset.sql_query.get("sql"), preset.sql_query.get("params")
                )
                # get number of alerts and number of noisy alerts
                elastic_sql_query = f"""select count(*),  MAX(CASE WHEN isNoisy = true AND dismissed = false AND deleted = false THEN 1 ELSE 0 END) from "keep-alerts-{self.tenant_id}" where {query}"""
                results = self.elastic_client.run_query(elastic_sql_query)
                preset.alerts_count = results["rows"][0][0]
                preset.should_do_noise_now = results["rows"][0][1] == 1
        self.logger.info("Finished searching alerts for presets")
        return presets

    def _create_raw_sql(self, sql_template, params):
        """
        Replace placeholders in the SQL template with actual values from the params dictionary.
        """
        for key, value in params.items():
            placeholder = f":{key}"
            if isinstance(value, str):
                value = f"'{value}'"  # Add quotes around string values
            sql_template = sql_template.replace(placeholder, str(value))
        return sql_template
