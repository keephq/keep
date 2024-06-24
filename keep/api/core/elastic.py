import logging
import os

from elasticsearch import BadRequestError, Elasticsearch
from elasticsearch.helpers import bulk

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.rulesengine.rulesengine import RulesEngine


class ElasticClient:
    _instance = None
    _client = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ElasticClient, cls).__new__(cls)
        return cls._instance

    def __init__(
        self, api_key=None, hosts: list[str] = None, basic_auth=None, **kwargs
    ):
        if self._client is not None:
            return

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
            self._client = Elasticsearch(
                basic_auth=basic_auth, hosts=self.hosts, **kwargs
            )
        else:
            self.logger.debug("Using API key for Elastic")
            self._client = Elasticsearch(
                api_key=self.api_key, hosts=self.hosts, **kwargs
            )

    def _construct_alert_dto_from_results(self, results, fields):
        if not results:
            return []

        alert_dtos = []

        for result in results["hits"]["hits"]:
            alert = result["fields"]
            for field in alert:
                # Shahar: this is another constraint
                # as elasticsearch returns a list for each field
                # if the list contains only one element, we take the element
                # we can overcome it by specific mapping in the index
                # but this is a good workaround for now
                try:
                    if len(alert[field]) == 1:
                        alert[field] = alert[field][0]
                except TypeError:
                    self.logger.warning(f"Failed to parse field {field}")
            # translate severity
            try:
                alert["severity"] = AlertSeverity.from_number(
                    int(alert["severity"])
                ).value
            # backward compatibility
            except Exception:
                alert["severity"] = AlertSeverity[alert["severity"].upper()].value
            # source is a list
            if not isinstance(alert["source"], list):
                alert["source"] = [alert["source"]]

            # now handle nested fields
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
            # Shahar: since ES does not return None's, we will add them manually:
            for field in fields:
                if field not in nested_alert:
                    nested_alert[field] = None
            # finally, build the dto
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
            results = self._client.sql.query(
                body={
                    "query": query,
                    "field_multi_value_leniency": True,
                    "fetch_size": limit,
                }
            )
            return results
        except BadRequestError as e:
            # means no index. if no alert was indexed, the index is not exist
            if "Unknown index" in str(e):
                self.logger.warning("Index does not exist yet.")
                return []
            else:
                self.logger.error(f"Failed to run query in Elastic: {e}")
                raise Exception(f"Failed to run query in Elastic: {e}")
        except Exception as e:
            self.logger.error(f"Failed to run query in Elastic: {e}")
            raise Exception(f"Failed to run query in Elastic: {e}")

    def search_alerts(self, tenant_id: str, query: str, limit: int) -> list[AlertDto]:
        if not self.enabled:
            return

        try:
            # Shahar: due to limitation in Elasticsearch array fields, we translate the SQL to DSL
            #         this is not 100% efficient since there are two requests (translate + query) instead of one but this could be improved with
            #         either:
            #           1. get the ES query from the client (react query builder support it)
            #           2. use the translate when keeping the preset in the db since its not change (only for presets, not general queryes)
            #           3. wait for ES to support array fields in SQL
            # TODO - https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            # preprocess severity
            query = RulesEngine.preprocess_cel_expression(query)
            dsl_query = self._client.sql.translate(
                body={"query": query, "fetch_size": limit}
            )
            fields = [f.get("field") for f in dict(dsl_query)["fields"]]
            raw_alerts = self._client.search(
                index=f"keep-alerts-{tenant_id}", body=dict(dsl_query)
            )
            alerts_dtos = self._construct_alert_dto_from_results(raw_alerts, fields)
            return alerts_dtos
        except BadRequestError as e:
            # means no index. if no alert was indexed, the index is not exist
            if "Unknown index" in str(e):
                self.logger.warning("Index does not exist yet.")
                return []
            else:
                self.logger.error(f"Failed to run query in Elastic: {e}")
                raise Exception(f"Failed to run query in Elastic: {e}")
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
            self._client.index(
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
            success, failed = bulk(self._client, actions, refresh="true")
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
        alert = self._client.get(index=f"keep-alerts-{tenant_id}", id=alert_fingerprint)
        if not alert:
            self.logger.error(f"Alert with fingerprint {alert_fingerprint} not found")
            return

        # enrich the alert
        alert["_source"].update(alert_enrichments)
        enriched_alert = AlertDto(**alert["_source"])
        # index the enriched alert
        self.index_alert(tenant_id, enriched_alert)
        self.logger.debug(f"Alert {alert_fingerprint} enriched and indexed")

    def drop_index(self, tenant_id):
        if not self.enabled:
            return

        self._client.indices.delete(index=f"keep-alerts-{tenant_id}")
