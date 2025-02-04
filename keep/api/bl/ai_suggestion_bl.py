import hashlib
import json
import logging
import uuid
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import HTTPException
from openai import OpenAI, OpenAIError
from sqlmodel import Session

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.db import get_session_sync
from keep.api.models.alert import (
    AlertDto,
    IncidentCandidate,
    IncidentClustering,
    IncidentDto,
    IncidentsClusteringSuggestion,
)
from keep.api.models.db.ai_suggestion import AIFeedback, AISuggestion, AISuggestionType
from keep.api.models.db.topology import TopologyServiceDtoOut


class AISuggestionBl:
    def __init__(self, tenant_id: str, session: Session | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.session = session if session else get_session_sync()

        # Todo: interface it with any model
        #       https://github.com/keephq/keep/issues/2373
        # Todo: per-tenant keys
        #       https://github.com/keephq/keep/issues/2365
        # Todo: also goes with settings page
        #       https://github.com/keephq/keep/issues/2365
        try:
            self._client = OpenAI()
        except OpenAIError as e:
            # if its api key error, we should raise 400
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            raise HTTPException(
                status_code=400, detail="AI service is not enabled for the client."
            )

    def get_suggestion_by_input(self, suggestion_input: Dict) -> Optional[AISuggestion]:
        """
        Retrieve an AI suggestion by its input.

        Args:
        - suggestion_input (Dict): The input of the suggestion.

        Returns:
        - Optional[AISuggestion]: The suggestion object if found, otherwise None.
        """
        suggestion_input_hash = self.hash_suggestion_input(suggestion_input)
        return (
            self.session.query(AISuggestion)
            .filter(
                AISuggestion.tenant_id == self.tenant_id,
                AISuggestion.suggestion_input_hash == suggestion_input_hash,
            )
            .first()
        )

    def hash_suggestion_input(self, suggestion_input: Dict) -> str:
        """
        Hash the suggestion input to allow for duplicate suggestions with the same input.

        Args:
        - suggestion_input (Dict): The input of the suggestion.

        Returns:
        - str: The hash of the suggestion input.
        """

        json_input = json.dumps(suggestion_input, sort_keys=True)
        return hashlib.sha256(json_input.encode()).hexdigest()

    def add_suggestion(
        self,
        user_id: str,
        suggestion_input: Dict,
        suggestion_type: AISuggestionType,
        suggestion_content: Dict,
        model: str,
    ) -> AISuggestion:
        """
        Add a new AI suggestion to the database.

        Args:
        - suggestion_type (AISuggestionType): The type of suggestion.
        - suggestion_content (Dict): The content of the suggestion.
        - model (str): The model used for the suggestion.

        Returns:
        - AISuggestion: The created suggestion object.
        """
        self.logger.info(
            "Adding new AI suggestion",
            extra={
                "tenant_id": self.tenant_id,
                "suggestion_type": suggestion_type,
            },
        )

        try:
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
            self.session.add(suggestion)
            self.session.commit()
            self.logger.info(
                "AI suggestion added successfully",
                extra={
                    "tenant_id": self.tenant_id,
                    "suggestion_id": suggestion.id,
                },
            )
            return suggestion
        except Exception as e:
            self.logger.error(
                "Failed to add AI suggestion",
                extra={
                    "tenant_id": self.tenant_id,
                    "error": str(e),
                },
            )
            self.session.rollback()
            raise

    def add_feedback(
        self,
        suggestion_id: UUID,
        user_id: str,
        feedback_content: str,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
    ) -> AIFeedback:
        """
        Add AI feedback to the database.

        Args:
        - suggestion_id (UUID): The ID of the suggestion being feedback on.
        - user_id (str): The ID of the user providing feedback.
        - feedback_content (str): The feedback content.
        - rating (Optional[int]): The user's rating of the AI suggestion.
        - comment (Optional[str]): Any additional comments from the user.

        Returns:
        - AIFeedback: The created feedback object.
        """
        self.logger.info(
            "Saving AI feedback",
            extra={
                "tenant_id": self.tenant_id,
                "suggestion_id": suggestion_id,
            },
        )

        try:
            feedback = AIFeedback(
                suggestion_id=suggestion_id,
                user_id=user_id,
                feedback_content=feedback_content,
                rating=rating,
                comment=comment,
            )
            self.session.add(feedback)
            self.session.commit()
            self.logger.info(
                "AI feedback saved successfully",
                extra={
                    "tenant_id": self.tenant_id,
                    "feedback_id": feedback.id,
                },
            )
            return feedback
        except Exception as e:
            self.logger.error(
                "Failed to save AI feedback",
                extra={
                    "tenant_id": self.tenant_id,
                    "error": str(e),
                },
            )
            self.session.rollback()
            raise

    def get_feedback(
        self, suggestion_type: AISuggestionType | None = None
    ) -> List[AIFeedback]:
        """
        Retrieve AI feedback from the database.

        Args:
        - suggestion_type (AISuggestionType | None): Optional filter for suggestion type.

        Returns:
        - List[AIFeedback]: List of feedback objects.
        """
        query = (
            self.session.query(AIFeedback)
            .join(AISuggestion)
            .filter(AISuggestion.tenant_id == self.tenant_id)
        )

        if suggestion_type:
            query = query.filter(AISuggestion.suggestion_type == suggestion_type)

        feedback_list = query.all()

        self.logger.info(
            "Retrieved AI feedback",
            extra={
                "tenant_id": self.tenant_id,
                "feedback_count": len(feedback_list),
                "suggestion_type": suggestion_type,
            },
        )

        return feedback_list

    def suggest_incidents(
        self,
        alerts_dto: List[AlertDto],
        topology_data: List[TopologyServiceDtoOut],
        user_id: str,
    ) -> IncidentsClusteringSuggestion:
        """Create incident suggestions using AI."""
        if len(alerts_dto) > 50:
            raise HTTPException(status_code=400, detail="Too many alerts to process")

        # Check for existing suggestion
        alerts_fingerprints = [alert.fingerprint for alert in alerts_dto]
        suggestion_input = {"alerts_fingerprints": alerts_fingerprints}
        existing_suggestion = self.get_suggestion_by_input(suggestion_input)

        if existing_suggestion:
            self.logger.info("Retrieving existing suggestion from DB")
            incident_clustering = IncidentClustering.parse_obj(
                existing_suggestion.suggestion_content
            )
            processed_incidents = self._process_incidents(
                incident_clustering.incidents, alerts_dto
            )
            return IncidentsClusteringSuggestion(
                incident_suggestion=processed_incidents,
                suggestion_id=str(existing_suggestion.id),
            )

        try:
            # Prepare prompts
            system_prompt, user_prompt = self._prepare_prompts(
                alerts_dto, topology_data
            )

            # Get completion from OpenAI
            completion = self._get_ai_completion(system_prompt, user_prompt)

            # Parse and process response
            incident_clustering = IncidentClustering.parse_raw(
                completion.choices[0].message.content
            )

            # Save suggestion
            suggestion = self.add_suggestion(
                user_id=user_id,
                suggestion_input=suggestion_input,
                suggestion_type=AISuggestionType.INCIDENT_SUGGESTION,
                suggestion_content=incident_clustering.dict(),
                model="gpt-4o-2024-08-06",
            )

            # Process incidents
            processed_incidents = self._process_incidents(
                incident_clustering.incidents, alerts_dto
            )

            return IncidentsClusteringSuggestion(
                incident_suggestion=processed_incidents,
                suggestion_id=str(suggestion.id),
            )

        except Exception as e:
            self.logger.error(f"AI incident creation failed: {e}")
            raise HTTPException(status_code=500, detail="AI service is unavailable.")

    async def commit_incidents(
        self,
        suggestion_id: UUID,
        incidents_with_feedback: List[Dict],
        user_id: str,
        incident_bl: IncidentBl,
    ) -> List[IncidentDto]:
        """Commit incidents with user feedback."""
        committed_incidents = []

        # Add feedback to the database
        changes = {
            incident_commit["incident"]["id"]: incident_commit["changes"]
            for incident_commit in incidents_with_feedback
        }
        self.add_feedback(
            suggestion_id=suggestion_id,
            user_id=user_id,
            feedback_content=changes,
        )

        for incident_with_feedback in incidents_with_feedback:
            if not incident_with_feedback["accepted"]:
                self.logger.info(
                    f"Incident {incident_with_feedback['incident']['name']} rejected by user, skipping creation"
                )
                continue

            try:
                # Create the incident
                incident_dto = IncidentDto.parse_obj(incident_with_feedback["incident"])
                created_incident = incident_bl.create_incident(
                    incident_dto, generated_from_ai=True
                )

                # Add alerts to the created incident
                alert_ids = [
                    alert["fingerprint"]
                    for alert in incident_with_feedback["incident"]["alerts"]
                ]
                await incident_bl.add_alerts_to_incident(created_incident.id, alert_ids)

                committed_incidents.append(created_incident)
                self.logger.info(
                    f"Incident {incident_with_feedback['incident']['name']} created successfully"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to create incident {incident_with_feedback['incident']['name']}: {str(e)}"
                )

        return committed_incidents

    def _prepare_prompts(
        self, alerts_dto: List[AlertDto], topology_data: List[TopologyServiceDtoOut]
    ) -> Tuple[str, str]:
        """Prepare system and user prompts for AI."""
        alert_descriptions = "\n".join(
            [
                f"Alert {idx+1}: {json.dumps(alert.dict())}"
                for idx, alert in enumerate(alerts_dto)
            ]
        )

        topology_text = "\n".join(
            [
                f"Topology {idx+1}: {json.dumps(topology.dict(), default=str)}"
                for idx, topology in enumerate(topology_data)
            ]
        )

        system_prompt = """
        You are an advanced AI system specializing in IT operations and incident management.
        Your task is to analyze the provided IT operations alerts and topology data, and cluster them into meaningful incidents.
        Consider factors such as:
        1. Alert description and content
        2. Potential temporal proximity
        3. Affected systems or services
        4. Type of IT issue (e.g., performance degradation, service outage, resource utilization)
        5. Potential root causes
        6. Relationships and dependencies between services in the topology data

        Group related alerts into distinct incidents and provide a detailed analysis for each incident.
        For each incident:
        1. Assess its severity
        2. Recommend initial actions for the IT operations team
        3. Provide a confidence score (0.0 to 1.0) for the incident clustering
        4. Explain how the confidence score was calculated, considering factors like alert similarity, topology relationships, and the strength of the correlation between alerts

        Use the topology data to improve your incident clustering by considering service dependencies and relationships.
        """

        user_prompt = f"""
        Analyze the following IT operations alerts and topology data, then group the alerts into incidents:

        Alerts:
        {alert_descriptions}

        Topology data:
        {topology_text}

        Provide your analysis and clustering in the specified JSON format.
        """

        return system_prompt, user_prompt

    def _get_ai_completion(self, system_prompt: str, user_prompt: str):
        """Get completion from OpenAI."""
        return self._client.chat.completions.create(
            model="gpt-4o-2024-08-06",
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
                                            "enum": [
                                                "critical",
                                                "high",
                                                "warning",
                                                "info",
                                                "low",
                                            ],
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

    def _process_incidents(
        self, incidents: List[IncidentCandidate], alerts_dto: List[AlertDto]
    ) -> List[IncidentDto]:
        """Process incidents and create DTOs."""
        processed_incidents = []
        for incident in incidents:
            alert_sources: Set[str] = set()
            alert_services: Set[str] = set()
            for alert_index in incident.alerts:
                alert = alerts_dto[alert_index - 1]
                if alert.source:
                    alert_sources.add(alert.source[0])
                if alert.service:
                    alert_services.add(alert.service)

            incident_alerts = [alerts_dto[i - 1] for i in incident.alerts]
            start_time = min(alert.lastReceived for alert in incident_alerts)
            last_seen_time = max(alert.lastReceived for alert in incident_alerts)

            incident_dto = IncidentDto(
                id=uuid.uuid4(),
                name=incident.incident_name,
                start_time=start_time,
                last_seen_time=last_seen_time,
                description=incident.reasoning,
                confidence_score=incident.confidence_score,
                confidence_explanation=incident.confidence_explanation,
                severity=incident.severity,
                alert_ids=[alerts_dto[i - 1].id for i in incident.alerts],
                recommended_actions=incident.recommended_actions,
                is_predicted=True,
                is_confirmed=False,
                alerts_count=len(incident.alerts),
                alert_sources=list(alert_sources),
                alerts=incident_alerts,
                services=list(alert_services),
            )
            processed_incidents.append(incident_dto)
        return processed_incidents
