import asyncio
import logging
import os
import pathlib
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional, Set
from uuid import UUID

from fastapi import HTTPException
from pusher import Pusher
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, select

from keep.api.arq_pool import get_pool
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import (
    add_alerts_to_incident,
    add_audit,
    create_incident_from_dto,
    delete_incident_by_id,
    enrich_alerts_with_incidents,
    get_all_alerts_by_fingerprints,
    get_incident_by_id,
    get_incident_unique_fingerprint_count,
    is_all_alerts_resolved,
    is_first_incident_alert_resolved,
    is_last_incident_alert_resolved,
    remove_alerts_to_incident_by_incident_id,
    update_incident_from_dto_by_id,
    update_incident_severity,
)
from keep.api.core.elastic import ElasticClient
from keep.api.core.incidents import get_last_incidents_by_cel
from keep.api.models.action_type import ActionType
from keep.api.models.db.incident import Incident, IncidentSeverity, IncidentStatus
from keep.api.models.db.rule import ResolveOn
from keep.api.models.incident import IncidentDto, IncidentDtoIn, IncidentSorting
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.pagination import IncidentsPaginatedResultsDto
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.workflowmanager.workflowmanager import WorkflowManager

logger = logging.getLogger(__name__)

MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION = int(
    os.environ.get("MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION", "5")
)

# Normalize env parsing
EE_ENABLED = os.environ.get("EE_ENABLED", "false").strip().lower() == "true"
REDIS_ENABLED = os.environ.get("REDIS", "false").strip().lower() == "true"

if EE_ENABLED:
    path_with_ee = str(pathlib.Path(__file__).parent.resolve()) + "/../../../ee/experimental"
    sys.path.insert(0, path_with_ee)
    ALGORITHM_VERBOSE_NAME = os.environ.get("ALGORITHM_VERBOSE_NAME")
else:
    # Correct fallback: NotImplemented is NOT a normal sentinel.
    ALGORITHM_VERBOSE_NAME = None


def _ensure_uuid(value: UUID | str, field_name: str = "id") -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from e


@contextmanager
def _commit_or_rollback(session: Session, logger_: logging.Logger, ctx: str):
    """
    Ensures rollback on exception; commits are explicit.
    """
    try:
        yield
    except Exception:
        logger_.exception("DB operation failed: %s", ctx)
        session.rollback()
        raise


class IncidentBl:
    """
    Session ownership:
    - This class does NOT close the session. Caller owns it.
    - This class WILL rollback on failed operations where it controls the transaction boundary.

    Workflow recursion guard:
    - Prevents internal workflow-triggered cascades from looping forever.
    """

    _workflow_guard: Set[str] = set()

    def __init__(
        self,
        tenant_id: str,
        session: Session,
        pusher_client: Optional[Pusher] = None,
        user: str = None,
    ):
        self.tenant_id = tenant_id
        self.user = user
        self.session = session
        self.pusher_client = pusher_client
        self.logger = logging.getLogger(__name__)
        self.ee_enabled = EE_ENABLED
        self.redis = REDIS_ENABLED

    # ---------------------------
    # Core helpers (side effects)
    # ---------------------------

    def __update_elastic(self, alert_fingerprints: List[str]) -> None:
        """
        Elasticsearch update is a side effect.
        It must not break the main DB operation once the DB is committed.
        """
        try:
            elastic_client = ElasticClient(self.tenant_id)
            if not getattr(elastic_client, "enabled", False):
                return

            db_alerts = get_all_alerts_by_fingerprints(
                tenant_id=self.tenant_id,
                fingerprints=alert_fingerprints,
                session=self.session,
            )
            db_alerts = enrich_alerts_with_incidents(
                self.tenant_id, db_alerts, session=self.session
            )
            enriched_alerts_dto = convert_db_alerts_to_dto_alerts(
                db_alerts, with_incidents=True
            )
            elastic_client.index_alerts(alerts=enriched_alerts_dto)
        except Exception:
            self.logger.exception(
                "Failed to push alerts to Elasticsearch (side effect)",
                extra={"tenant_id": self.tenant_id, "fingerprints": alert_fingerprints},
            )

    def update_client_on_incident_change(self, incident_id: Optional[UUID] = None) -> None:
        """
        Pusher is a side effect. Never raise.
        """
        if self.pusher_client is None:
            return
        try:
            self.pusher_client.trigger(
                f"private-{self.tenant_id}",
                "incident-change",
                {"incident_id": str(incident_id) if incident_id else None},
            )
        except Exception:
            self.logger.exception(
                "Failed to push incident change to client (side effect)",
                extra={
                    "tenant_id": self.tenant_id,
                    "incident_id": str(incident_id) if incident_id else None,
                },
            )

    def send_workflow_event(self, incident_dto: IncidentDto, action: str) -> None:
        """
        Workflows are side effects. Never raise.
        Includes recursion guard to prevent cascade loops.
        """
        guard_key = f"{self.tenant_id}:{incident_dto.id}:{action}"
        if guard_key in self._workflow_guard:
            self.logger.warning(
                "Workflow recursion guard blocked duplicate workflow event",
                extra={"tenant_id": self.tenant_id, "incident_id": str(incident_dto.id), "action": action},
            )
            return

        self._workflow_guard.add(guard_key)
        try:
            workflow_manager = WorkflowManager.get_instance()
            workflow_manager.insert_incident(self.tenant_id, incident_dto, action)
        except Exception:
            self.logger.exception(
                "Failed to run workflows based on incident (side effect)",
                extra={"tenant_id": self.tenant_id, "incident_id": str(incident_dto.id), "action": action},
            )
        finally:
            # Always remove guard so next legitimate event can pass later
            self._workflow_guard.discard(guard_key)

    def __postprocess_alerts_change(self, incident: Incident, alert_fingerprints: List[str]) -> None:
        self.__update_elastic(alert_fingerprints)
        self.update_client_on_incident_change(incident.id)
        incident_dto = IncidentDto.from_db_incident(incident)
        self.send_workflow_event(incident_dto, "updated")

    def __postprocess_incident_change(self, incident: Incident) -> IncidentDto:
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        incident_dto = IncidentDto.from_db_incident(incident)
        self.update_client_on_incident_change(incident.id)
        self.send_workflow_event(incident_dto, "updated")
        return incident_dto

    # ---------------------------
    # CRUD
    # ---------------------------

    def create_incident(
        self,
        incident_dto: IncidentDtoIn | IncidentDto,
        generated_from_ai: bool = False,
    ) -> IncidentDto:
        self.logger.info("Creating incident", extra={"tenant_id": self.tenant_id})

        with _commit_or_rollback(self.session, self.logger, "create_incident"):
            incident = create_incident_from_dto(
                self.tenant_id,
                incident_dto,
                generated_from_ai=generated_from_ai,
                session=self.session,
            )
            self.session.commit()

        incident_dto_out = IncidentDto.from_db_incident(incident)
        self.update_client_on_incident_change()
        self.send_workflow_event(incident_dto_out, "created")
        return incident_dto_out

    def sync_add_alerts_to_incident(self, *args, **kwargs) -> None:
        """
        Safe sync wrapper for async method.
        If inside an event loop, schedule it.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.add_alerts_to_incident(*args, **kwargs))
            return
        loop.create_task(self.add_alerts_to_incident(*args, **kwargs))

    async def add_alerts_to_incident(
        self,
        incident_id: UUID,
        alert_fingerprints: List[str],
        is_created_by_ai: bool = False,
        override_count: bool = False,
    ) -> None:
        incident_id = _ensure_uuid(incident_id, "incident_id")
        self.logger.info(
            "Adding alerts to incident",
            extra={"tenant_id": self.tenant_id, "incident_id": str(incident_id)},
        )

        with _commit_or_rollback(self.session, self.logger, "add_alerts_to_incident"):
            incident = get_incident_by_id(
                tenant_id=self.tenant_id,
                incident_id=incident_id,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")

            add_alerts_to_incident(
                self.tenant_id,
                incident,
                alert_fingerprints,
                is_created_by_ai,
                session=self.session,
                override_count=override_count,
            )

            # Explicit boundary
            self.session.commit()

        self.__postprocess_alerts_change(incident, alert_fingerprints)
        await self.__generate_summary(incident_id, incident)

    async def __generate_summary(self, incident_id: UUID, incident: Incident) -> None:
        try:
            fingerprints_count = get_incident_unique_fingerprint_count(
                self.tenant_id, incident_id, session=self.session
            )

            if (
                self.ee_enabled
                and self.redis
                and fingerprints_count > MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION
                and not incident.user_summary
            ):
                pool = await get_pool()
                job = await pool.enqueue_job(
                    "process_summary_generation",
                    tenant_id=self.tenant_id,
                    incident_id=incident_id,
                )
                self.logger.info(
                    "Summary generation scheduled",
                    extra={"tenant_id": self.tenant_id, "incident_id": str(incident_id), "job": str(job)},
                )
        except Exception:
            self.logger.exception(
                "Failed to generate summary for incident (side effect)",
                extra={"tenant_id": self.tenant_id, "incident_id": str(incident_id)},
            )

    def delete_alerts_from_incident(self, incident_id: UUID, alert_fingerprints: List[str]) -> None:
        incident_id = _ensure_uuid(incident_id, "incident_id")

        with _commit_or_rollback(self.session, self.logger, "delete_alerts_from_incident"):
            incident = get_incident_by_id(
                tenant_id=self.tenant_id,
                incident_id=incident_id,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")

            remove_alerts_to_incident_by_incident_id(
                self.tenant_id,
                incident_id,
                alert_fingerprints,
                session=self.session,
            )
            self.session.commit()

        self.__postprocess_alerts_change(incident, alert_fingerprints)

    def delete_incident(self, incident_id: UUID) -> None:
        incident_id = _ensure_uuid(incident_id, "incident_id")

        with _commit_or_rollback(self.session, self.logger, "delete_incident"):
            incident = get_incident_by_id(
                tenant_id=self.tenant_id,
                incident_id=incident_id,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")

            incident_dto = IncidentDto.from_db_incident(incident)

            deleted = delete_incident_by_id(
                tenant_id=self.tenant_id,
                incident_id=incident_id,
                session=self.session,
            )
            if not deleted:
                raise HTTPException(status_code=404, detail="Incident not found")

            self.session.commit()

        self.update_client_on_incident_change()
        self.send_workflow_event(incident_dto, "deleted")

    def update_incident(
        self,
        incident_id: UUID,
        updated_incident_dto: IncidentDtoIn,
        generated_by_ai: bool,
    ) -> IncidentDto:
        incident_id = _ensure_uuid(incident_id, "incident_id")

        with _commit_or_rollback(self.session, self.logger, "update_incident"):
            incident = update_incident_from_dto_by_id(
                self.tenant_id,
                incident_id,
                updated_incident_dto,
                generated_by_ai,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")
            self.session.commit()

        return self.__postprocess_incident_change(incident)

    def update_severity(
        self,
        incident_id: UUID,
        severity: IncidentSeverity,
        comment: Optional[str] = None,
    ) -> IncidentDto:
        incident_id = _ensure_uuid(incident_id, "incident_id")

        with _commit_or_rollback(self.session, self.logger, "update_severity"):
            incident = update_incident_severity(
                self.tenant_id,
                incident_id,
                severity,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")

            if comment:
                add_audit(
                    self.tenant_id,
                    str(incident_id),
                    self.user,
                    ActionType.INCIDENT_COMMENT,
                    comment,
                    session=self.session,
                    commit=False,
                )

            self.session.add(incident)
            self.session.commit()

        return self.__postprocess_incident_change(incident)

    # ---------------------------
    # Query
    # ---------------------------

    @staticmethod
    def query_incidents(
        tenant_id: str,
        limit: int = 25,
        offset: int = 0,
        timeframe: int = None,
        upper_timestamp: datetime = None,
        lower_timestamp: datetime = None,
        is_candidate: bool = False,
        sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
        with_alerts: bool = False,
        is_predicted: bool = None,
        cel: str = None,
        allowed_incident_ids: Optional[List[str]] = None,
    ):
        incidents, total_count = get_last_incidents_by_cel(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            timeframe=timeframe,
            upper_timestamp=upper_timestamp,
            lower_timestamp=lower_timestamp,
            is_candidate=is_candidate,
            sorting=sorting,
            with_alerts=with_alerts,
            is_predicted=is_predicted,
            cel=cel,
            allowed_incident_ids=allowed_incident_ids,
        )

        incidents_dto = [IncidentDto.from_db_incident(i) for i in incidents]
        return IncidentsPaginatedResultsDto(
            limit=limit, offset=offset, count=total_count, items=incidents_dto
        )

    # ---------------------------
    # Resolution logic
    # ---------------------------

    def _lock_incident_row(self, incident_id: UUID) -> Optional[Incident]:
        """
        Optional TOCTOU mitigation: row lock.
        Uses SELECT ... FOR UPDATE if the backend supports it.
        """
        try:
            stmt = select(Incident).where(Incident.id == incident_id).with_for_update()
            return self.session.exec(stmt).first()
        except Exception:
            # If dialect doesn't support it or model differs, fail gracefully.
            return None

    def resolve_incident_if_require(self, incident: Incident, max_retries: int = 3) -> Incident:
        """
        Attempts to resolve incident if criteria met.
        Includes:
        - retry on StaleDataError phantom update
        - re-check condition right before commit (TOCTOU mitigation)
        - optional row locking
        """
        incident_id = incident.id

        def _should_resolve(obj: Incident) -> bool:
            if obj.resolve_on == ResolveOn.ALL.value:
                return is_all_alerts_resolved(incident=obj, session=self.session)
            if obj.resolve_on == ResolveOn.FIRST.value:
                return is_first_incident_alert_resolved(obj, session=self.session)
            if obj.resolve_on == ResolveOn.LAST.value:
                return is_last_incident_alert_resolved(obj, session=self.session)
            return False

        if not _should_resolve(incident):
            return incident

        for attempt in range(max_retries):
            try:
                locked = self._lock_incident_row(incident_id) or incident

                if not _should_resolve(locked):
                    return locked

                locked.status = IncidentStatus.RESOLVED.value
                locked.end_time = locked.end_time or datetime.now(tz=timezone.utc)
                self.session.add(locked)
                self.session.commit()
                return locked

            except StaleDataError as ex:
                msg = ex.args[0] if ex.args else ""
                self.session.rollback()

                if "expected to update" in str(msg):
                    self.logger.info(
                        "Phantom read detected while resolving incident, retrying",
                        extra={"tenant_id": self.tenant_id, "incident_id": str(incident_id), "attempt": attempt + 1},
                    )
                    if attempt == max_retries - 1:
                        raise
                    continue
                raise

            except Exception:
                self.session.rollback()
                raise

        return incident

    def change_status(
        self,
        incident_id: UUID | str,
        new_status: IncidentStatus,
        change_by: AuthenticatedEntity,
    ) -> IncidentDto:
        incident_id_uuid = _ensure_uuid(incident_id, "incident_id")
        with_alerts = new_status in [IncidentStatus.RESOLVED, IncidentStatus.ACKNOWLEDGED]

        with _commit_or_rollback(self.session, self.logger, "change_status"):
            incident = get_incident_by_id(
                self.tenant_id,
                incident_id_uuid,
                with_alerts=with_alerts,
                session=self.session,
            )
            if not incident:
                raise HTTPException(status_code=404, detail="Incident not found")

            if new_status in [IncidentStatus.RESOLVED, IncidentStatus.ACKNOWLEDGED]:
                enrichments = {"status": new_status.value}
                fingerprints = [a.fingerprint for a in (incident.alerts or [])]

                enrichments_bl = EnrichmentsBl(self.tenant_id, db=self.session)
                action_type, action_description, *_ = enrichments_bl.get_enrichment_metadata(
                    enrichments, change_by
                )
                enrichments_bl.batch_enrich(
                    fingerprints,
                    enrichments,
                    action_type,
                    change_by.email,
                    action_description,
                    dispose_on_new_alert=True,
                )

            if new_status == IncidentStatus.RESOLVED:
                incident.end_time = datetime.now(tz=timezone.utc)

            current_assignee = incident.assignee
            new_assignee = change_by.email

            if current_assignee != new_assignee and new_assignee:
                incident.assignee = new_assignee
                add_audit(
                    self.tenant_id,
                    str(incident_id_uuid),
                    new_assignee,
                    ActionType.INCIDENT_ASSIGN,
                    f"Incident self-assigned to {new_assignee}",
                    session=self.session,
                    commit=False,
                )

            add_audit(
                self.tenant_id,
                str(incident_id_uuid),
                change_by.email,
                ActionType.INCIDENT_STATUS_CHANGE,
                f"Incident status changed from {incident.status} to {new_status.value}",
                session=self.session,
                commit=False,
            )

            incident.status = new_status.value
            self.session.add(incident)
            self.session.commit()

        return self.__postprocess_incident_change(incident)