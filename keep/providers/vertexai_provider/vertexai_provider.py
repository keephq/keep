"""
VertexAI Provider for Keep.

Supports all LLMs served through Google Cloud Vertex AI, including:
- Gemini models (gemini-1.5-pro, gemini-1.0-pro, etc.)
- Text models (text-bison, chat-bison, etc.)
- Third-party models served through Model Garden

Authentication supports:
- Service Account JSON key (for explicit credentials)
- Workload Identity / ADC (Application Default Credentials) when running on GKE/GCE
"""

import dataclasses
import json
import logging
import os
from typing import Optional

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class VertexaiProviderAuthConfig:
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google Cloud Project ID",
            "sensitive": False,
        },
    )
    location: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Google Cloud region for Vertex AI (e.g. us-central1)",
            "sensitive": False,
        },
        default="us-central1",
    )
    service_account_json: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": (
                "Service Account JSON key (leave empty to use Workload Identity "
                "or Application Default Credentials when running on GKE/GCE)"
            ),
            "sensitive": True,
        },
        default=None,
    )


class VertexaiProvider(BaseProvider):
    """Query Google Cloud Vertex AI LLMs from Keep workflows."""

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VertexaiProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        return {}

    def _get_vertexai_client(self):
        """
        Return an initialised vertexai GenerativeModel client.

        Uses service account JSON if provided, otherwise falls back to
        Application Default Credentials (Workload Identity on GKE, etc.).
        """
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is required for the Vertex AI provider. "
                "Install it with: pip install google-cloud-aiplatform"
            )

        sa_json = self.authentication_config.service_account_json
        if sa_json:
            # Explicit service-account credentials
            try:
                from google.oauth2 import service_account

                sa_info = json.loads(sa_json)
                credentials = service_account.Credentials.from_service_account_info(
                    sa_info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                vertexai.init(
                    project=self.authentication_config.project_id,
                    location=self.authentication_config.location,
                    credentials=credentials,
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to parse service_account_json: {e}"
                )
        else:
            # Use Application Default Credentials (Workload Identity, gcloud auth, etc.)
            vertexai.init(
                project=self.authentication_config.project_id,
                location=self.authentication_config.location,
            )

        return GenerativeModel

    def _query(
        self,
        prompt: str,
        model: str = "gemini-1.5-pro",
        max_tokens: int = 1024,
        structured_output_format: Optional[dict] = None,
    ):
        """
        Query a Vertex AI LLM with the given prompt.

        Args:
            prompt: The prompt to send to the model.
            model: Vertex AI model name (default: gemini-1.5-pro).
            max_tokens: Maximum number of output tokens.
            structured_output_format: Optional JSON schema for structured output.
                When provided the model is instructed to return valid JSON
                matching the schema (same interface as the OpenAI/Gemini providers).

        Returns:
            dict with key ``response`` containing the model output (str or parsed JSON).
        """
        from vertexai.generative_models import GenerationConfig

        GenerativeModel = self._get_vertexai_client()

        actual_prompt = prompt
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            actual_prompt = (
                f"You must respond with valid JSON that matches this schema: "
                f"{json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else.\n\n"
                f"User query: {prompt}"
            )

        generative_model = GenerativeModel(model)
        response = generative_model.generate_content(
            actual_prompt,
            generation_config=GenerationConfig(max_output_tokens=max_tokens),
        )

        content = response.text

        try:
            content = json.loads(content)
        except Exception:
            pass

        return {"response": content}


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # When running locally, set GOOGLE_CLOUD_PROJECT and authenticate via:
    #   gcloud auth application-default login
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]

    config = ProviderConfig(
        description="Vertex AI Provider",
        authentication={
            "project_id": project_id,
            "location": "us-central1",
            # service_account_json is optional – omit to use ADC / Workload Identity
        },
    )

    provider = VertexaiProvider(
        context_manager=context_manager,
        provider_id="vertexai_provider",
        config=config,
    )

    result = provider.query(
        prompt=(
            "Here is an alert, classify the severity: "
            "Clients are getting 500 errors on the checkout page."
        ),
        model="gemini-1.5-pro",
        structured_output_format={
            "type": "json_schema",
            "json_schema": {
                "name": "severity_classification",
                "schema": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                    },
                    "required": ["severity"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        max_tokens=100,
    )
    print(result)
