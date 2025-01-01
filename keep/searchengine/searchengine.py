import enum
import logging

from keep.api.core.db import get_last_alerts
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.elastic import ElasticClient
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.preset import PresetDto, PresetSearchQuery
from keep.api.models.time_stamp import TimeStampFilter
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine


class SearchMode(enum.Enum):
    """The search mode for the search engine"""

    # use elastic to search alerts (for large tenants)
    ELASTIC = "elastic"
    # use internal search to search alerts (for small-medium tenants)
    INTERNAL = "internal"


class SearchEngine:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)
        self.rule_engine = RulesEngine(tenant_id=self.tenant_id)
        self.elastic_client = ElasticClient(tenant_id)
        self.tenant_configuration = TenantConfiguration()
        # this is backward compatibility for single/noauth tenants
        if tenant_id == SINGLE_TENANT_UUID:
            self.search_mode = (
                SearchMode.ELASTIC
                if self.elastic_client.enabled
                else SearchMode.INTERNAL
            )
        # elif elastic is disabled:
        elif not self.elastic_client.enabled:
            self.search_mode = SearchMode.INTERNAL
        # for multi-tenant deployment with elastic enabled, get the per-tenant search configuration:
        else:
            search_mode_config = self.tenant_configuration.get_configuration(
                tenant_id, "search_mode"
            )
            if search_mode_config:
                self.search_mode = SearchMode(search_mode_config)
            else:
                self.search_mode = SearchMode.INTERNAL
        self.logger.info(
            "Initialized search engine",
            extra={"tenant_id": self.tenant_id, "search_mode": self.search_mode},
        )

    def _get_last_alerts(
        self, limit=1000, timeframe: int = 0, time_stamp: TimeStampFilter = None
    ) -> list[AlertDto]:
        """Get the last alerts

        Returns:
            list[AlertDto]: The list of alerts
        """
        self.logger.info("Getting last alerts")
        lower_timestamp = time_stamp.lower_timestamp if time_stamp else None
        upper_timestamp = time_stamp.upper_timestamp if time_stamp else None

        alerts = get_last_alerts(
            tenant_id=self.tenant_id,
            limit=limit,
            timeframe=timeframe,
            lower_timestamp=lower_timestamp,
            upper_timestamp=upper_timestamp,
            with_incidents=True,
            optimized=True,
        )
        self.logger.info("Finished querying last alerts, converting to DTO")
        # convert the alerts to DTO
        alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
        self.logger.info(
            f"Finished getting last alerts {lower_timestamp} {upper_timestamp} {time_stamp}"
        )
        return alerts_dto

    def search_alerts_by_cel(
        self,
        cel_query: str,
        alerts: list[AlertDto] = None,
        limit: int = 1000,
        timeframe: int = 0,
    ) -> list[AlertDto]:
        """Search for alerts based on a CEL query

        Args:
            cel_query (str): The CEL query to search for
            alerts (list[AlertDto]): The list of alerts to search in

        Returns:
            list[AlertDto]: The list of alerts that match the query
        """
        self.logger.info("Searching alerts by CEL")
        # if alerts are not provided
        if alerts is None:
            # get the alerts
            alerts = self._get_last_alerts(limit=limit, timeframe=timeframe)
        # filter the alerts
        filtered_alerts = self.rule_engine.filter_alerts(alerts, cel_query)
        self.logger.info("Finished searching alerts by CEL")
        return filtered_alerts

    def _search_alerts_by_sql(
        self, sql_query: dict, limit=1000, timeframe: int = 0
    ) -> list[AlertDto]:
        """Search for alerts based on a SQL query

        Args:
            sql_query (dict): The SQL query to search for

        Returns:
            list[AlertDto]: The list of alerts that match the query
        """
        self.logger.info("Searching alerts by SQL")
        query = self._create_raw_sql(sql_query.get("sql"), sql_query.get("params"))
        # get the alerts from elastic
        elastic_sql_query = (
            f"""select * from "{self.elastic_client.alerts_index}" """
            + (f"where {query}" if query else "")
        )
        if timeframe:
            elastic_sql_query += f" and lastReceived > now() - {timeframe}s"

        elastic_sql_query += f" order by lastReceived desc limit {limit}"
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("elastic_run_query"):
            filtered_alerts = self.elastic_client.search_alerts(
                elastic_sql_query, limit
            )
        self.logger.info("Finished searching alerts by SQL")
        return filtered_alerts

    def search_alerts(self, query: PresetSearchQuery) -> list[AlertDto]:
        """Search for alerts based on a query

        Args:
            query (dict | str): CEL (str) / SQL (dict) query

        Returns:
            list[AlertDto]: The list of alerts that match the query
        """
        self.logger.info("Searching alerts")
        # if internal
        if self.search_mode == SearchMode.INTERNAL:
            filtered_alerts = self.search_alerts_by_cel(
                query.cel_query, limit=query.limit, timeframe=query.timeframe
            )
        # if elastic
        elif self.search_mode == SearchMode.ELASTIC:
            filtered_alerts = self._search_alerts_by_sql(
                query.sql_query, limit=query.limit, timeframe=query.timeframe
            )
        else:
            self.logger.error("Invalid search mode")
            return []
        self.logger.info("Finished searching alerts")
        return filtered_alerts

    def search_preset_alerts(
        self, presets: list[PresetDto], time_stamp: TimeStampFilter = None
    ) -> dict[str, list[AlertDto]]:
        """Search for alerts based on a list of queries

        Args:
            presets (list[Preset]): The list of presets to search for

        Returns:
            dict[str, list[AlertDto]]: The list of alerts that match each query
        """
        self.logger.info(
            "Searching alerts for presets",
            extra={"tenant_id": self.tenant_id, "search_mode": self.search_mode},
        )

        # if internal
        if self.search_mode == SearchMode.INTERNAL:
            # get the alerts
            alerts_dto = self._get_last_alerts(time_stamp=time_stamp)
            # performance optimization: get the alerts activation once
            alerts_activation = self.rule_engine.get_alerts_activation(alerts_dto)
            for preset in presets:
                filtered_alerts = self.rule_engine.filter_alerts(
                    alerts_dto, preset.cel_query, alerts_activation
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
                try:
                    query = self._create_raw_sql(
                        preset.sql_query.get("sql"), preset.sql_query.get("params")
                    )
                    # get number of alerts and number of noisy alerts
                    elastic_sql_query = (
                        f"""select count(*),  MAX(CASE WHEN isNoisy = true AND dismissed = false AND deleted = false THEN 1 ELSE 0 END) from "{self.elastic_client.alerts_index}" """
                        + (f" where {query}" if query else "")
                    )
                    results = self.elastic_client.run_query(elastic_sql_query)
                    if results:
                        preset.alerts_count = results["rows"][0][0]
                        preset.should_do_noise_now = results["rows"][0][1] == 1
                    else:
                        self.logger.warning(
                            "No results found for preset",
                            extra={"preset_id": preset.id, "preset_name": preset.name},
                        )
                        preset.alerts_count = 0
                        preset.should_do_noise_now = False
                except Exception:
                    self.logger.exception(
                        "Failed to search alerts for preset",
                        extra={"preset_id": preset.id, "preset_name": preset.name},
                    )
                    pass
        self.logger.info(
            "Finished searching alerts for presets",
            extra={"tenant_id": self.tenant_id, "search_mode": self.search_mode},
        )
        return presets

    def _create_raw_sql(self, sql_template, params):
        """
        Replace placeholders in the SQL template with actual values from the params dictionary.
        """
        params = list(params.items())
        # param_{double_digit} bug
        params.reverse()
        if params:
            for key, value in params:
                placeholder = f":{key}"
                if isinstance(value, str):
                    value = f"'{value}'"  # Add quotes around string values
                sql_template = sql_template.replace(placeholder, str(value))
        return sql_template
