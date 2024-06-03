import logging
import os

from elasticsearch import Elasticsearch

from keep.api.models.alert import AlertDto


class ElasticClient:

    def __init__(
        self, api_key=None, hosts: list[str] = None, basic_auth=None, **kwargs
    ):
        # elastic is disabled by default
        self.enabled = os.environ.get("ELASTIC_ENABLED", "false").lower() == "true"
        if not self.enabled:
            return
        self.api_key = api_key or os.environ.get("ELASTIC_API_KEY")
        self.hosts = hosts or os.environ.get("ELASTIC_HOSTS").split(",")

        basic_auth = basic_auth or (
            os.environ.get("ELASTIC_USER"),
            os.environ.get("ELASTIC_PASSWORD"),
        )
        if not (self.api_key or basic_auth) or not self.hosts:
            raise ValueError(
                "No Elastic configuration found although Elastic is enabled"
            )
        self.logger = logging.getLogger(__name__)

        if basic_auth:
            self.client = Elasticsearch(
                basic_auth=basic_auth, hosts=self.hosts, **kwargs
            )
        else:
            self.client = Elasticsearch(
                api_key=self.api_key, hosts=self.hosts, **kwargs
            )

    def _construct_alert_dto_from_results(self, results):
        columns = results["columns"]
        columns = [col["name"] for col in columns]
        rows = results["rows"]
        if not rows:
            return []
        alert_dtos = []

        for row in rows:
            alert = dict(zip(columns, row))
            # see https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            # should be solved in the future
            alert["source"] = [alert["source"]]
            alert_dtos.append(AlertDto(**alert))

        return alert_dtos

    def run_query(self, query: str):
        if not self.enabled:
            return

        try:
            # TODO - handle source (array)
            # TODO - https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            results = self.client.sql.query(
                body={"query": query, "field_multi_value_leniency": True}
            )
            return results
        except Exception as e:
            self.logger.error(f"Failed to run query in Elastic: {e}")
            raise Exception(f"Failed to run query in Elastic: {e}")

    def search_alerts(self, query: str) -> list[AlertDto]:
        if not self.enabled:
            return

        try:
            # TODO - handle source (array)
            # TODO - https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            raw_alerts = self.client.sql.query(
                body={"query": query, "field_multi_value_leniency": True}
            )
            alerts_dtos = self._construct_alert_dto_from_results(raw_alerts)
            return alerts_dtos
        except Exception as e:
            self.logger.error(f"Failed to search alerts in Elastic: {e}")
            raise Exception(f"Failed to search alerts in Elastic: {e}")

    def index_alert(self, tenant_id, alert: AlertDto):
        if not self.enabled:
            return

        try:
            self.client.index(
                index=f"keep-alerts-{tenant_id}",
                body=alert.dict(),
                id=alert.fingerprint,  # we want to update the alert if it already exists so that elastic will have the latest version
            )
        # TODO: retry/pubsub
        except Exception as e:
            self.logger.error(f"Failed to index alert to Elastic: {e}")
            raise Exception(f"Failed to index alert to Elastic: {e}")

    def index_alerts(self, tenant_id, alerts: list[AlertDto]):
        if not self.enabled:
            return

        for alert in alerts:
            self.index_alert(tenant_id, alert)

    def enrich_alert(self, tenant_id, alert_fingerprint: str, alert_enrichments: dict):
        if not self.enabled:
            return

        self.logger.debug(f"Enriching alert {alert_fingerprint}")
        # get the alert, enrich it and index it
        alert = self.client.get(index=f"keep-alerts-{tenant_id}", id=alert_fingerprint)
        if not alert:
            self.logger.error(f"Alert with fingerprint {alert_fingerprint} not found")
            return

        # enrich the alert
        enriched_alert = alert["_source"].update(alert_enrichments)
        # index the enriched alert
        self.index_alert(tenant_id, enriched_alert)
        self.logger.debug(f"Alert {alert_fingerprint} enriched and indexed")
