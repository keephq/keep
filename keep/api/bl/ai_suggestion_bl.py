import asyncio
import hashlib
import json
import logging
import os
import uuid
from contextlib import AbstractContextManager
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import HTTPException
from openai import OpenAI, OpenAIError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.consts import OPENAI_MODEL_NAME
from keep.api.core.db import get_session_sync
from keep.api.models.alert import AlertDto
from keep.api.models.db.ai_suggestion import AIFeedback, AISuggestion, AISuggestionType
from keep.api.models.db.topology import TopologyServiceDtoOut
from keep.api.models.incident import (
    IncidentCandidate,
    IncidentClustering,
    IncidentDto,
    IncidentsClusteringSuggestion,
)


class AISuggestionBl(AbstractContextManager):
    """
    Business logic for AI suggestions and incident clustering.

    IMPORTANT:
    - If this class creates its own Session, it owns it and will close it.
    - Suggestion caching requires a DB unique constraint on (tenant_id, suggestion_input_hash).
    """

    DEFAULT_ALERT_LIMIT = int(os.getenv("KEEP_AI_ALERT_LIMIT", "50"))

    def __init__(self, tenant_id: str, session: Session | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id

        self._owns_session = session is None
        self.session: Session = session if session is not None else get_session_sync()

        try:
            self._client = OpenAI()
        except OpenAIError as e:
            # Most common cause: missing/invalid key
            self.logger.error("Failed to initialize OpenAI client: %s", str(e))
            raise HTTPException(
                status_code=400,
                detail="AI service is not enabled for this tenant/client.",
            ) from e

    # ---------- session lifecycle ----------

    def close(self) -> None:
        if self._owns_session:
            try:
                self.session.close()
            except Exception:
                self.logger.exception("Failed closing owned DB session")

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ---------- helpers ----------

    @staticmethod
    def hash_suggestion_input(suggestion_input: Dict[str, Any]) -> str:
        json_input = json.dumps(suggestion_input, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_input.encode("utf-8")).hexdigest()

    def get_suggestion_by_input(self, suggestion_input: Dict[str, Any]) -> Optional[AISuggestion]:
        suggestion_input_hash = self.hash_suggestion_input(suggestion_input)
        return (
            self.session.query(AISuggestion)
            .filter(
                AISuggestion.tenant_id == self.tenant_id,
                AISuggestion.suggestion_input_hash == suggestion_input_hash,
            )
            .first()
        )

    # ---------- DB writes (sync) ----------

    def add_suggestion(
        self,
        user_id: str,
        suggestion_input: Dict[str, Any],
        suggestion_type: AISuggestionType,
        suggestion_content: Dict[str, Any],
        model: str,
    ) -> AISuggestion:
        """
        Insert suggestion. Requires unique constraint on (tenant_id, suggestion_input_hash).
        """
        suggestion_input_hash = self.hash_suggestion_input(suggestion_input)

        suggestion = AISuggestion(
            tenant_id=self.tenant_id,
            user_id=user_id,
            suggestion_input=suggestion_input,
            suggestion_input_hash=suggestion_input_hash,
            suggestion_type=suggestion_type,
            suggestion_content=suggestion_content,
            model=model,
        )

        try:
            self.session.add(suggestion)
            self.session.commit()
            self.session.refresh(suggestion)
            return suggestion
        except IntegrityError:
            # Another request inserted the same hash concurrently
            self.session.rollback()
            existing = (
                self.session.query(AISuggestion)
                .filter(
                    AISuggestion.tenant_id == self.tenant_id,
                    AISuggestion.suggestion_input_hash == suggestion_input_hash,
                )
                .first()
            )
            if existing:
                return existing
            raise
        except Exception:
            self.session.rollback()
            raise

    def add_feedback(
        self,
        suggestion_id: UUID,
        user_id: str,
        feedback_content: Any,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
    ) -> AIFeedback:
        feedback = AIFeedback(
            suggestion_id=suggestion_id,
            user_id=user_id,
            feedback_content=feedback_content,
            rating=rating,
            comment=comment,
        )
        try:
            self.session.add(feedback)
            self.session.flush()  # do not commit here; caller decides transaction scope
            return feedback
        except Exception:
            self.session.rollback()
            raise

    # ---------- public API ----------

    def suggest_incidents(
        self,
        alerts_dto: List[AlertDto],
        topology_data: List[TopologyServiceDtoOut],
        user_id: str,
        alert_limit: Optional[int] = None,
    ) -> IncidentsClusteringSuggestion:
        """
        Create incident suggestions using AI or return cached suggestion.
        """
        limit = alert_limit if alert_limit is not None else self.DEFAULT_ALERT_LIMIT
        if len(alerts_dto) > limit:
            raise HTTPException(
                status_code=400,
                detail=f"Too many alerts to process (max {limit}).",
            )

        alerts_fingerprints = [a.fingerprint for a in alerts_dto]
        suggestion_input: Dict[str, Any] = {"alerts_fingerprints": alerts_fingerprints}

        cached = self.get_suggestion_by_input(suggestion_input)
        if cached:
            self.logger.info("Returning cached AI suggestion", extra={"tenant_id": self.tenant_id})
            incident_clustering = IncidentClustering.parse_obj(cached.suggestion_content)
            processed = self._process_incidents(incident_clustering.incidents, alerts_dto)
            return IncidentsClusteringSuggestion(
                incident_suggestion=processed,
                suggestion_id=str(cached.id),
            )

        # Not cached: compute via AI
        try:
            system_prompt, user_prompt = self._prepare_prompts(alerts_dto, topology_data)
            completion = self._get_ai_completion(system_prompt, user_prompt)

            content = completion.choices[0].message.content
            if not content:
                raise ValueError("AI returned empty response content")

            incident_clustering = IncidentClustering.parse_raw(content)

            # Save suggestion (race-safe via unique constraint + IntegrityError handling)
            suggestion = self.add_suggestion(
                user_id=user_id,
                suggestion_input=suggestion_input,
                suggestion_type=AISuggestionType.INCIDENT_SUGGESTION,
                suggestion_content=incident_clustering.dict(),
                model=OPENAI_MODEL_NAME,
            )

            processed = self._process_incidents(incident_clustering.incidents, alerts_dto)

            if not processed:
                # Not fatal, but worth signaling
                self.logger.warning(
                    "AI returned no valid incidents after processing",
                    extra={"tenant_id": self.tenant_id, "suggestion_id": str(suggestion.id)},
                )

            return IncidentsClusteringSuggestion(
                incident_suggestion=processed,
                suggestion_id=str(suggestion.id),
            )

        except OpenAIError as e:
            self.logger.error("OpenAI API error: %s", str(e))
            raise HTTPException(status_code=503, detail="AI service is unavailable.") from e
        except (ValueError, json.JSONDecodeError) as e:
            self.logger.error("Invalid AI response format: %s", str(e))
            raise HTTPException(status_code=500, detail="Invalid AI response format.") from e
        except HTTPException:
            raise
        except Exception as e:
            self.logger.exception("AI incident creation failed unexpectedly: %s", str(e))
            raise HTTPException(status_code=500, detail="AI service is unavailable.") from e

    async def commit_incidents(
        self,
        suggestion_id: UUID,
        incidents_with_feedback: List[Dict[str, Any]],
        user_id: str,
        incident_bl: IncidentBl,
    ) -> List[IncidentDto]:
        """
        Commit incidents with user feedback as a single unit of work.

        Strategy:
        - Run sync DB work in a thread pool so we don't block the event loop.
        - Wrap feedback creation + incident creation in a transaction.
        - If any accepted incident fails, rollback everything (no partial state).
        """
        if not incidents_with_feedback:
            return []

        loop = asyncio.get_running_loop()

        def _sync_unit_of_work() -> List[IncidentDto]:
            committed: List[IncidentDto] = []

            try:
                # Begin transactional scope.
                # For SQLAlchemy/SQLModel sessions, commit/rollback controls the transaction.
                changes = {
                    ic["incident"].get("id"): ic.get("changes")
                    for ic in incidents_with_feedback
                    if ic.get("incident")
                }

                # Feedback should not commit alone; flush only.
                self.add_feedback(
                    suggestion_id=suggestion_id,
                    user_id=user_id,
                    feedback_content=changes,
                )

                # Create accepted incidents only
                for item in incidents_with_feedback:
                    if not item.get("accepted"):
                        continue

                    incident_payload = item.get("incident")
                    if not incident_payload:
                        raise ValueError("Missing incident payload in commit request")

                    incident_dto = IncidentDto.parse_obj(incident_payload)

                    created = incident_bl.create_incident(incident_dto, generated_from_ai=True)
                    committed.append(created)

                # Commit DB work (feedback + incidents)
                self.session.commit()
                return committed

            except Exception:
                self.session.rollback()
                raise

        # Run sync DB creation work off the event loop
        try:
            created_incidents: List[IncidentDto] = await loop.run_in_executor(None, _sync_unit_of_work)
        except HTTPException:
            raise
        except Exception as e:
            self.logger.exception("Failed committing incidents: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to commit incidents.") from e

        # Now attach alerts (async) to each created incident
        # Use consistent identifier type. Here we use fingerprints everywhere.
        # If your incident_bl expects DB IDs instead, change this in ONE place, not two.
        try:
            # Map incident id -> alert fingerprints from payload
            for item in incidents_with_feedback:
                if not item.get("accepted"):
                    continue
                incident_payload = item.get("incident") or {}
                incident_name = incident_payload.get("name")

                # Find corresponding created incident by name or by payload id (preferred if stable)
                # If payload includes 'id' that matches created_incident.id, use it.
                # Otherwise fallback to name match.
                payload_id = incident_payload.get("id")

                target = None
                if payload_id:
                    # created_incident.id may be UUID; normalize to string compare
                    for ci in created_incidents:
                        if str(ci.id) == str(payload_id):
                            target = ci
                            break

                if target is None and incident_name:
                    for ci in created_incidents:
                        if getattr(ci, "name", None) == incident_name:
                            target = ci
                            break

                if target is None:
                    raise ValueError("Could not map committed incident to payload for alert attachment")

                alerts_list = incident_payload.get("alerts") or []
                alert_fingerprints = [a.get("fingerprint") for a in alerts_list if isinstance(a, dict)]
                alert_fingerprints = [fp for fp in alert_fingerprints if fp]

                await incident_bl.add_alerts_to_incident(target.id, alert_fingerprints)

        except Exception as e:
            # At this point incidents exist; alert attachment failed.
            # Depending on desired behavior, you could:
            # - return incidents anyway (with a warning)
            # - or raise and let the caller handle remediation
            self.logger.exception("Failed attaching alerts to incidents: %s", str(e))
            raise HTTPException(status_code=500, detail="Incidents created, but failed attaching alerts.") from e

        return created_incidents

    # ---------- AI prompt + response ----------

    def _prepare_prompts(
        self,
        alerts_dto: List[AlertDto],
        topology_data: List[TopologyServiceDtoOut],
    ) -> Tuple[str, str]:
        alert_descriptions = "\n".join(
            [f"Alert {idx+1}: {json.dumps(alert.dict())}" for idx, alert in enumerate(alerts_dto)]
        )

        topology_text = "\n".join(
            [
                f"Topology {idx+1}: {json.dumps(topology.dict(), default=str)}"
                for idx, topology in enumerate(topology_data)
            ]
        )

        system_prompt = """
You are an AI system specializing in IT operations and incident management.
Cluster the provided alerts into incidents using alert content and topology dependencies.

Return JSON matching the provided schema. Alert indices are 1-based.
"""

        user_prompt = f"""
Analyze the following IT operations alerts and topology data, then group the alerts into incidents.

Alerts:
{alert_descriptions}

Topology data:
{topology_text}
"""

        return system_prompt.strip(), user_prompt.strip()

    def _get_ai_completion(self, system_prompt: str, user_prompt: str):
        return self._client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_clustering",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "incidents": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "incident_name": {"type": "string"},
                                        "alerts": {
                                            "type": "array",
                                            "items": {"type": "integer"},
                                            "description": "List of alert numbers (1-based index)",
                                        },
                                        "reasoning": {"type": "string"},
                                        "severity": {
                                            "type": "string",
                                            "enum": ["critical", "high", "warning", "info", "low"],
                                        },
                                        "recommended_actions": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "confidence_score": {"type": "number"},
                                        "confidence_explanation": {"type": "string"},
                                    },
                                    "required": [
                                        "incident_name",
                                        "alerts",
                                        "reasoning",
                                        "severity",
                                        "recommended_actions",
                                        "confidence_score",
                                        "confidence_explanation",
                                    ],
                                },
                            }
                        },
                        "required": ["incidents"],
                    },
                },
            },
            temperature=0.2,
        )

    # ---------- incident processing ----------

    def _process_incidents(
        self,
        incidents: List[IncidentCandidate],
        alerts_dto: List[AlertDto],
    ) -> List[IncidentDto]:
        processed: List[IncidentDto] = []
        n_alerts = len(alerts_dto)

        for incident in incidents:
            # Validate indices and de-duplicate
            valid_indices: List[int] = []
            for idx in incident.alerts:
                if not isinstance(idx, int):
                    self.logger.warning("Non-integer alert index from AI: %r", idx)
                    continue
                if idx < 1 or idx > n_alerts:
                    self.logger.warning(
                        "Invalid alert index from AI: %s (valid range 1..%s)",
                        idx,
                        n_alerts,
                    )
                    continue
                valid_indices.append(idx)

            valid_indices = sorted(set(valid_indices))
            if not valid_indices:
                # Skip empty incidents (AI hallucinated indices or got filtered)
                self.logger.info("Skipping incident with no valid alert indices: %s", incident.incident_name)
                continue

            incident_alerts = [alerts_dto[i - 1] for i in valid_indices]

            alert_sources: Set[str] = set()
            alert_services: Set[str] = set()

            for a in incident_alerts:
                # source can be None, list, str... be defensive
                src = getattr(a, "source", None)
                if isinstance(src, list) and src:
                    alert_sources.add(str(src[0]))
                elif isinstance(src, str) and src:
                    alert_sources.add(src)

                svc = getattr(a, "service", None)
                if isinstance(svc, str) and svc:
                    alert_services.add(svc)

            start_time = min(a.lastReceived for a in incident_alerts)
            last_seen_time = max(a.lastReceived for a in incident_alerts)

            # IMPORTANT: avoid storing full alert objects unless you really need it.
            # If API expects it, keep it; otherwise prefer IDs/fingerprints.
            incident_dto = IncidentDto(
                id=uuid.uuid4(),
                name=incident.incident_name,
                start_time=start_time,
                last_seen_time=last_seen_time,
                description=incident.reasoning,
                confidence_score=incident.confidence_score,
                confidence_explanation=incident.confidence_explanation,
                severity=incident.severity,
                # Choose ONE identifier strategy:
                # - IDs: [a.id ...]
                # - fingerprints: [a.fingerprint ...]
                alert_ids=[a.fingerprint for a in incident_alerts],
                recommended_actions=incident.recommended_actions,
                is_predicted=True,
                is_candidate=True,
                is_visible=True,
                alerts_count=len(valid_indices),
                alert_sources=list(alert_sources),
                # Keep alerts only if needed by API response contract
                alerts=incident_alerts,
                services=list(alert_services),
            )
            processed.append(incident_dto)

        return processed