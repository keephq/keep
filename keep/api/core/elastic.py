import logging
import os

from elasticsearch import ApiError, BadRequestError, Elasticsearch
from elasticsearch.helpers import BulkIndexError, bulk

from keep.api.core.db import get_enrichments
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto, AlertSeverity
from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.api.utils.enrichment_helpers import parse_and_enrich_deleted_and_assignees


class ElasticClient:

    def __init__(
        self,
        tenant_id,
        api_key=None,
        hosts: list[str] = None,
        basic_auth=None,
        **kwargs,
    ):
        self.tenant_id = tenant_id
        self.tenant_configuration = TenantConfiguration()
        self.logger = logging.getLogger(__name__)

        enabled = os.environ.get("ELASTIC_ENABLED", "false").lower() == "true"

        # if its a single tenant deployment or elastic is disabled, return
        if tenant_id == SINGLE_TENANT_UUID:
            self.enabled = enabled
        # if its a multi tenant deployment and elastic is on, check if its enabled for the tenant
        elif not enabled:
            self.enabled = False
        # else, pre tenant configuration
        else:
            # if elastic is disabled for the tenant, return
            if not self.tenant_configuration.get_configuration(
                tenant_id, "search_mode"
            ):
                self.enabled = False
                self.logger.debug(f"Elastic is disabled for tenant {tenant_id}")
                return
            else:
                self.enabled = True

        # if elastic is disabled, return
        if not self.enabled:
            return

        self.api_key = api_key or os.environ.get("ELASTIC_API_KEY")
        self.hosts = hosts or os.environ.get("ELASTIC_HOSTS").split(",")
        self.verify_certs = (
            os.environ.get("ELASTIC_VERIFY_CERTS", "true").lower() == "true"
        )

        basic_auth = basic_auth or (
            os.environ.get("ELASTIC_USER"),
            os.environ.get("ELASTIC_PASSWORD"),
        )
        if not (self.api_key or basic_auth) or not self.hosts:
            raise ValueError(
                "No Elastic configuration found although Elastic is enabled"
            )

        # single tenant id should have an index suffix
        if tenant_id == SINGLE_TENANT_UUID and not os.environ.get(
            "ELASTIC_INDEX_SUFFIX"
        ):
            raise ValueError(
                "No Elastic index suffix found although Elastic is enabled for single tenant"
            )

        if any(basic_auth):
            self.logger.debug("Using basic auth for Elastic")
            self._client = Elasticsearch(
                basic_auth=basic_auth,
                hosts=self.hosts,
                verify_certs=self.verify_certs,
                **kwargs,
            )
        else:
            self.logger.debug("Using API key for Elastic")
            self._client = Elasticsearch(
                api_key=self.api_key,
                hosts=self.hosts,
                verify_certs=self.verify_certs,
                **kwargs,
            )

    @property
    def alerts_index(self):
        if self.tenant_id == SINGLE_TENANT_UUID:
            suffix = os.environ.get("ELASTIC_INDEX_SUFFIX")
            return f"keep-alerts-{suffix}"
        else:
            return f"keep-alerts-{self.tenant_id}"

    def _construct_alert_dto_from_results(self, results):
        if not results:
            return []
        alert_dtos = []

        fingerprints = [
            result["_source"]["fingerprint"] for result in results["hits"]["hits"]
        ]
        enrichments = get_enrichments(self.tenant_id, fingerprints)
        enrichments_by_fingerprint = {
            enrichment.alert_fingerprint: enrichment.enrichments
            for enrichment in enrichments
        }
        for result in results["hits"]["hits"]:
            alert = result["_source"]
            alert_dto = AlertDto(**alert)
            if alert_dto.fingerprint in enrichments_by_fingerprint:
                parse_and_enrich_deleted_and_assignees(
                    alert_dto, enrichments_by_fingerprint[alert_dto.fingerprint]
                )
            alert_dtos.append(alert_dto)
        return alert_dtos

    def run_query(self, query: str, limit: int = 1000):
        if not self.enabled:
            return

        # preprocess severity
        query = preprocess_cel_expression(query)

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
                self.logger.exception(
                    f"Failed to run query in Elastic: {e}",
                    extra={
                        "tenant_id": self.tenant_id,
                    },
                )
                raise Exception(f"Failed to run query in Elastic: {e}")
        except Exception as e:
            self.logger.exception(
                f"Failed to run query in Elastic: {e}",
                extra={
                    "tenant_id": self.tenant_id,
                },
            )
            raise Exception(f"Failed to run query in Elastic: {e}")

    def search_alerts(self, query: str, limit: int) -> list[AlertDto]:
        if not self.enabled:
            return []

        try:
            # Shahar: due to limitation in Elasticsearch array fields, we translate the SQL to DSL
            #         this is not 100% efficient since there are two requests (translate + query) instead of one but this could be improved with
            #         either:
            #           1. get the ES query from the client (react query builder support it)
            #           2. use the translate when keeping the preset in the db since its not change (only for presets, not general queryes)
            #           3. wait for ES to support array fields in SQL
            # TODO - https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-limitations.html#_array_type_of_fields
            # preprocess severity
            query = preprocess_cel_expression(query)
            dsl_query = self._client.sql.translate(
                body={"query": query, "fetch_size": limit}
            )
            # get all fields
            dsl_query = dict(dsl_query)
            dsl_query["_source"] = True
            dsl_query["fields"] = ["*"]

            raw_alerts = self._client.search(index=self.alerts_index, body=dsl_query)
            alerts_dtos = self._construct_alert_dto_from_results(raw_alerts)

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

    def index_alert(self, alert: AlertDto):
        if not self.enabled:
            return

        try:
            # query
            alert_dict = alert.dict()
            alert_dict["dismissed"] = bool(alert_dict["dismissed"])
            # change severity to number so we can sort by it
            alert_dict["severity"] = AlertSeverity(alert.severity.lower()).order
            self._client.index(
                index=self.alerts_index,
                body=alert_dict,
                id=alert.fingerprint,  # we want to update the alert if it already exists so that elastic will have the latest version
                refresh="true",
            )
        # TODO: retry/pubsub
        except ApiError as e:
            self.logger.error(f"Failed to index alert to Elastic: {e} {e.errors}")
            raise Exception(f"Failed to index alert to Elastic: {e} {e.errors}")
        except Exception as e:
            self.logger.error(f"Failed to index alert to Elastic: {e}")
            raise Exception(f"Failed to index alert to Elastic: {e}")

    def index_alerts(self, alerts: list[AlertDto]):
        if not self.enabled:
            return

        actions = []
        for alert in alerts:
            action = {
                "_index": self.alerts_index,
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
        except BulkIndexError as e:
            self.logger.error(f"Failed to index alerts to Elastic: {e} {e.errors}")
            raise Exception(f"Failed to index alerts to Elastic: {e} {e.errors}")
        except ApiError as e:
            self.logger.error(f"Failed to index alerts to Elastic: {e} {e.errors}")
            raise Exception(f"Failed to index alerts to Elastic: {e} {e.errors}")
        except Exception as e:
            self.logger.exception(f"Failed to index alerts to Elastic: {e}")
            raise Exception(f"Failed to index alerts to Elastic: {e}")

    def enrich_alert(self, alert_fingerprint: str, alert_enrichments: dict):
        if not self.enabled:
            return

        self.logger.debug(f"Enriching alert {alert_fingerprint}")
        # get the alert, enrich it and index it
        alert = self._client.get(index=self.alerts_index, id=alert_fingerprint)
        if not alert:
            self.logger.error(f"Alert with fingerprint {alert_fingerprint} not found")
            return

        # enrich the alert
        alert["_source"].update(alert_enrichments)
        enriched_alert = AlertDto(**alert["_source"])
        # index the enriched alert
        self.index_alert(enriched_alert)
        self.logger.debug(f"Alert {alert_fingerprint} enriched and indexed")

    def drop_index(self):
        if not self.enabled:
            return

        self._client.indices.delete(index=self.alerts_index)
