import logging
import os

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.rulesengine.rulesengine import RulesEngine


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
        # if basic auth is provided, use it, otherwise use api key
        if any(basic_auth):
            self.logger.debug("Using basic auth for Elastic")
            self.client = Elasticsearch(
                basic_auth=basic_auth, hosts=self.hosts, **kwargs
            )
        else:
            self.logger.debug("Using API key for Elastic")
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
            # Handle nested fields
            nested_alert = {}
            for key, value in alert.items():
                if "." in key:
                    parts = key.split(".")
                    d = nested_alert
                    for part in parts[:-1]:
                        if part not in d:
                            d[part] = {}
                        d = d[part]
                    d[parts[-1]] = value
                else:
                    nested_alert[key] = value

            # Ensure source is a list (due to limitations mentioned in Elasticsearch docs)
            if "source" in nested_alert:
                nested_alert["source"] = [nested_alert["source"]]

            # Translate severity to string
            if "severity" in nested_alert:
                nested_alert["severity"] = AlertSeverity.from_number(
                    nested_alert["severity"]
                ).value

            alert_dtos.append(AlertDto(**nested_alert))

        return alert_dtos

    def run_query(self, query: str, limit: int = 1000):
        if not self.enabled:
            return

        # preprocess severity
        query = RulesEngine.preprocess_cel_expression(query)

        try:
            # TODO - handle source (array)
            # TODO - https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            results = self.client.sql.query(
                body={
                    "query": query,
                    "field_multi_value_leniency": True,
                    "fetch_size": limit,
                }
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
            # change severity to number so we can sort by it
            alert.severity = AlertSeverity(alert.severity.lower()).order
            # query
            self.client.index(
                index=f"keep-alerts-{tenant_id}",
                body=alert.dict(),
                id=alert.fingerprint,  # we want to update the alert if it already exists so that elastic will have the latest version
                refresh="true",
            )
        # TODO: retry/pubsub
        except Exception as e:
            self.logger.error(f"Failed to index alert to Elastic: {e}")
            raise Exception(f"Failed to index alert to Elastic: {e}")

    def index_alerts(self, tenant_id, alerts: list[AlertDto]):
        if not self.enabled:
            return

        actions = []
        for alert in alerts:
            action = {
                "_index": f"keep-alerts-{tenant_id}",
                "_id": alert.fingerprint,  # use fingerprint as the document ID
                "_source": alert.dict(),
            }
            # change severity to number so we can sort by it
            action["_source"]["severity"] = AlertSeverity(
                action["_source"]["severity"].lower()
            ).order
            actions.append(action)

        try:
            success, failed = bulk(self.client, actions, refresh="true")
            self.logger.info(
                f"Successfully indexed {success} alerts. Failed to index {failed} alerts."
            )
        except Exception as e:
            self.logger.error(f"Failed to index alerts to Elastic: {e}")
            raise Exception(f"Failed to index alerts to Elastic: {e}")

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
        alert["_source"].update(alert_enrichments)
        enriched_alert = AlertDto(**alert["_source"])
        # index the enriched alert
        self.index_alert(tenant_id, enriched_alert)
        self.logger.debug(f"Alert {alert_fingerprint} enriched and indexed")
