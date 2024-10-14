import hashlib
import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlmodel import Session

from keep.api.core.db import get_session_sync
from keep.api.models.db.ai_suggestion import AIFeedback, AISuggestion, AISuggestionType


class AISuggestionBl:
    def __init__(self, tenant_id: str, session: Session | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.session = session if session else get_session_sync()

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
