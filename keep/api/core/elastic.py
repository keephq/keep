import logging
import os
from typing import Any, Optional

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
        tenant_id: str,
        api_key: Optional[str] = None,
        hosts: Optional[list[str]] = None,
        basic_auth: Optional[tuple[Optional[str], Optional[str]]] = None,
        **kwargs: Any,
    ):
        self.tenant_id = tenant_id
        self.tenant_configuration = TenantConfiguration()
        self.logger = logging.getLogger(__name__)

        self.enabled = self._is_enabled_for_tenant(tenant_id)
        if not self.enabled:
            self._client = None
            return

        self.refresh_strategy = self._parse_refresh_strategy(
            os.environ.get("ELASTIC_REFRESH_STRATEGY", "true")
        )

        self.api_key = api_key or os.environ.get("ELASTIC_API_KEY")

        # Hosts: explicit param wins, else env, else error
        self.hosts = hosts or self._parse_hosts(os.environ.get("ELASTIC_HOSTS"))
        if not self.hosts:
            raise ValueError("Elastic is enabled but ELASTIC_HOSTS is missing/empty")

        self.verify_certs = os.environ.get("ELASTIC_VERIFY_CERTS", "true").strip().lower() == "true"

        # Auth: explicit basic_auth wins, else env, else api_key
        env_user = os.environ.get("ELASTIC_USER")
        env_pass = os.environ.get("ELASTIC_PASSWORD")
        basic_auth = basic_auth or (env_user, env_pass)

        basic_user, basic_pass = basic_auth
        basic_auth_present = bool(basic_user) and bool(basic_pass)
        api_key_present = bool(self.api_key)

        if not basic_auth_present and not api_key_present:
            raise ValueError("Elastic is enabled but no auth provided (ELASTIC_API_KEY or ELASTIC_USER/ELASTIC_PASSWORD)")

        # Single-tenant requires a suffix
        if tenant_id == SINGLE_TENANT_UUID and not os.environ.get("ELASTIC_INDEX_SUFFIX"):
            raise ValueError("Elastic enabled for single tenant but ELASTIC_INDEX_SUFFIX is missing")

        if basic_auth_present:
            self.logger.debug("Using basic auth for Elastic")
            self._client = Elasticsearch(
                hosts=self.hosts,
                basic_auth=(basic_user, basic_pass),
                verify_certs=self.verify_certs,
                **kwargs,
            )
        else:
            self.logger.debug("Using API key for Elastic")
            self._client = Elasticsearch(
                hosts=self.hosts,
                api_key=self.api_key,
                verify_certs=self.verify_certs,
                **kwargs,
            )

    def _is_enabled_for_tenant(self, tenant_id: str) -> bool:
        enabled_globally = os.environ.get("ELASTIC_ENABLED", "false").strip().lower() == "true"
        if not enabled_globally:
            return False

        # Single tenant: global switch controls it
        if tenant_id == SINGLE_TENANT_UUID:
            return True

        # Multi tenant: must also be enabled per tenant
        try:
            search_mode = self.tenant_configuration.get_configuration(tenant_id, "search_mode")
        except Exception:
            self.logger.exception("Failed reading tenant configuration for Elastic", extra={"tenant_id": tenant_id})
            return False

        # Treat specific values as enabled. Adjust to match your real config.
        if isinstance(search_mode, str):
            return search_mode.strip().lower() in {"elastic", "elasticsearch", "search"}
        return bool(search_mode)

    def _parse_hosts(self, raw: Optional[str]) -> list[str]:
        if not raw:
            return []
        hosts = [h.strip() for h in raw.split(",") if h.strip()]
        return hosts

    def _parse_refresh_strategy(self, raw: Any) -> Any:
        # Elasticsearch refresh accepts True/False or "wait_for"
        if isinstance(raw, bool):
            return raw
        val = str(raw).strip().lower()
        if val in {"true", "1", "yes", "on"}:
            return True
        if val in {"false", "0", "no", "off"}:
            return False
        if val == "wait_for":
            return "wait_for"
        # default safe behavior
        self.logger.warning("Invalid ELASTIC_REFRESH_STRATEGY=%r, defaulting to True", raw)
        return True

    @property
    def alerts_index(self) -> str:
        if self.tenant_id == SINGLE_TENANT_UUID:
            suffix = os.environ.get("ELASTIC_INDEX_SUFFIX")
            return f"keep-alerts-{suffix}"
        return f"keep-alerts-{self.tenant_id}"

    def _construct_alert_dto_from_results(self, results: dict) -> list[AlertDto]:
        hits = (results or {}).get("hits", {}).get("hits", [])
        if not hits:
            return []

        fingerprints: list[str] = []
        sources: list[dict] = []
        for hit in hits:
            src = hit.get("_source") or {}
            fp = src.get("fingerprint")
            if fp:
                fingerprints.append(fp)
            sources.append(src)

        enrichments = get_enrichments(self.tenant_id, fingerprints) if fingerprints else []
        enrichments_by_fp = {
            enrichment.alert_fingerprint: enrichment.enrichments for enrichment in enrichments
        }

        alert_dtos: list[AlertDto] = []
        for src in sources:
            try:
                alert_dto = AlertDto(**src)
            except Exception:
                self.logger.exception("Failed constructing AlertDto from ES _source", extra={"tenant_id": self.tenant_id})
                continue

            enr = enrichments_by_fp.get(alert_dto.fingerprint)
            if enr:
                parse_and_enrich_deleted_and_assignees(alert_dto, enr)

            alert_dtos.append(alert_dto)

        return alert_dtos

    def run_query(self, query: str, limit: int = 1000) -> dict:
        if not self.enabled or not self._client:
            return {}

        query = preprocess_cel_expression(query)

        try:
            return self._client.sql.query(
                body={
                    "query": query,
                    "field_multi_value_leniency": True,
                    "fetch_size": limit,
                }
            )
        except BadRequestError as e:
            if "Unknown index" in str(e):
                self.logger.warning("Elastic index does not exist yet", extra={"tenant_id": self.tenant_id})
                return {"hits": {"hits": []}}
            self.logger.exception("Elastic SQL query failed", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to run query in Elastic") from e
        except Exception as e:
            self.logger.exception("Elastic SQL query failed", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to run query in Elastic") from e

    def search_alerts(self, query: str, limit: int) -> list[AlertDto]:
        if not self.enabled or not self._client:
            return []

        query = preprocess_cel_expression(query)

        try:
            dsl_query = self._client.sql.translate(body={"query": query, "fetch_size": limit})
            dsl_query = dict(dsl_query)
            dsl_query["_source"] = True
            dsl_query["fields"] = ["*"]

            raw = self._client.search(index=self.alerts_index, body=dsl_query)
            return self._construct_alert_dto_from_results(raw)

        except BadRequestError as e:
            if "Unknown index" in str(e):
                self.logger.warning("Elastic index does not exist yet", extra={"tenant_id": self.tenant_id})
                return []
            self.logger.exception("Failed searching alerts in Elastic", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to search alerts in Elastic") from e
        except Exception as e:
            self.logger.exception("Failed searching alerts in Elastic", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to search alerts in Elastic") from e

    def _severity_to_order(self, severity: Any) -> int:
        # Accept enum/string/int. Default to lowest order if unknown.
        try:
            if isinstance(severity, int):
                return severity
            if hasattr(severity, "value"):
                severity = severity.value
            return AlertSeverity(str(severity).strip().lower()).order
        except Exception:
            return AlertSeverity.low.order

    def index_alert(self, alert: AlertDto) -> None:
        if not self.enabled or not self._client:
            return

        try:
            doc = alert.dict()
            doc["dismissed"] = bool(doc.get("dismissed"))
            doc["severity"] = self._severity_to_order(doc.get("severity"))

            self._client.index(
                index=self.alerts_index,
                id=alert.fingerprint,
                document=doc,  # modern client supports `document`
                refresh=self.refresh_strategy,
            )
        except ApiError as e:
            self.logger.exception("Failed to index alert to Elastic", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to index alert to Elastic") from e
        except Exception as e:
            self.logger.exception("Failed to index alert to Elastic", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to index alert to Elastic") from e

    def index_alerts(self, alerts: list[AlertDto]) -> None:
        if not self.enabled or not self._client or not alerts:
            return

        actions: list[dict] = []
        for alert in alerts:
            src = alert.dict()

            # Don’t mutate DTOs. Normalize in the dict.
            if "incident_dto" in src and isinstance(src["incident_dto"], list):
                # If these are objects with .json(), convert safely
                converted = []
                for item in src["incident_dto"]:
                    try:
                        converted.append(item.json() if hasattr(item, "json") else item)
                    except Exception:
                        converted.append(str(item))
                src["incident_dto"] = converted

            src["severity"] = self._severity_to_order(src.get("severity"))

            actions.append(
                {
                    "_index": self.alerts_index,
                    "_id": src.get("fingerprint"),
                    "_source": src,
                }
            )

        try:
            success, failed = bulk(self._client, actions, refresh=self.refresh_strategy)
            self.logger.info(
                "Bulk indexed alerts",
                extra={"tenant_id": self.tenant_id, "success": success, "failed": failed},
            )
        except BulkIndexError as e:
            self.logger.exception("Bulk index failed", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to bulk index alerts to Elastic") from e
        except ApiError as e:
            self.logger.exception("Bulk index API error", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to bulk index alerts to Elastic") from e
        except Exception as e:
            self.logger.exception("Bulk index unexpected error", extra={"tenant_id": self.tenant_id})
            raise RuntimeError("Failed to bulk index alerts to Elastic") from e

    def enrich_alert(self, alert_fingerprint: str, alert_enrichments: dict) -> None:
        if not self.enabled or not self._client:
            return

        try:
            res = self._client.get(index=self.alerts_index, id=alert_fingerprint)
        except ApiError as e:
            self.logger.warning("Failed to fetch alert for enrichment", extra={"tenant_id": self.tenant_id})
            return

        src = (res or {}).get("_source")
        if not src:
            self.logger.error("Alert not found for enrichment", extra={"tenant_id": self.tenant_id, "fp": alert_fingerprint})
            return

        src.update(alert_enrichments)
        enriched = AlertDto(**src)
        self.index_alert(enriched)

    def drop_index(self) -> None:
        if not self.enabled or not self._client:
            return
        try:
            self._client.indices.delete(index=self.alerts_index)
        except ApiError as e:
            # Ignore "index not found" style errors
            self.logger.warning("Failed deleting index (may not exist)", extra={"tenant_id": self.tenant_id})