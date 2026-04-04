"""
VertexAiProvider is a provider that integrates Keep with Google Cloud Vertex AI.
Supports text generation, embeddings, and model invocation via the Vertex AI SDK.
"""

import json
import dataclasses
import logging

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class VertexAiProviderAuthConfig:
    """
    Google Cloud Vertex AI provider authentication configuration.
    Reference: https://cloud.google.com/vertex-ai/docs/authentication
    """

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google Cloud Project ID",
            "hint": "Your GCP project ID, e.g. 'my-project-123'",
        }
    )
    location: str = dataclasses.field(
        default="us-central1",
        metadata={
            "required": False,
            "description": "Google Cloud region for Vertex AI endpoint",
            "hint": "e.g. 'us-central1', 'europe-west4'",
        },
    )
    credentials_json: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Google Cloud service account credentials JSON (optional, uses ADC if not provided)",
            "hint": "Paste the full JSON content of your service account key file",
            "sensitive": True,
        },
    )


class VertexAiProvider(BaseProvider):
    """
    Invoke Google Cloud Vertex AI generative models from Keep workflows.
    Supports text generation, multi-modal prompts, and structured JSON output.
    """

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_CATEGORY = ["AI"]
    PROVIDER_TAGS = ["ai", "llm", "google"]
    DEFAULT_MODEL = "gemini-1.5-flash-001"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="aiplatform:predict",
            description="Required to invoke Vertex AI model endpoints",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://cloud.google.com/vertex-ai/docs/authentication",
            alias="Vertex AI User",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._vertex_client = None

    def validate_config(self):
        """Validates required configuration for Vertex AI provider."""
        self.authentication_config = VertexAiProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Nothing to dispose."""
        pass

    def _get_client(self):
        """Lazily initialise the Vertex AI SDK with project + credentials."""
        try:
            import vertexai
            from google.oauth2 import service_account
            import google.auth

            creds = None
            if self.authentication_config.credentials_json:
                info = json.loads(self.authentication_config.credentials_json)
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )

            vertexai.init(
                project=self.authentication_config.project_id,
                location=self.authentication_config.location,
                credentials=creds,
            )
            return vertexai
        except ImportError:
            raise RuntimeError(
                "google-cloud-aiplatform package is required for VertexAiProvider. "
                "Install it with: pip install google-cloud-aiplatform"
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            self._get_client()
            from vertexai.generative_models import GenerativeModel

            model = GenerativeModel(self.DEFAULT_MODEL)
            # Try a minimal generation to verify credentials & access
            model.generate_content(
                "Say 'ok'",
                generation_config={"max_output_tokens": 5},
            )
            scopes["aiplatform:predict"] = True
        except Exception as e:
            scopes["aiplatform:predict"] = str(e)
        return scopes

    def _query(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        structured_output_format: dict = None,
        system_instruction: str = None,
        **kwargs,
    ) -> dict:
        """
        Invoke a Vertex AI generative model with the given prompt.

        Args:
            prompt: Text prompt to send to the model.
            model: Vertex AI model name (default: gemini-1.5-flash-001).
            max_tokens: Maximum number of output tokens.
            temperature: Sampling temperature (0.0–1.0).
            structured_output_format: Optional JSON schema to enforce structured output.
            system_instruction: Optional system-level instruction for the model.

        Returns:
            dict with 'response' key containing the model output.
        """
        from vertexai.generative_models import GenerativeModel, GenerationConfig, Content, Part

        self._get_client()
        model_name = model or self.DEFAULT_MODEL

        # Build system instruction
        init_kwargs = {}
        if system_instruction:
            init_kwargs["system_instruction"] = system_instruction

        gemini = GenerativeModel(model_name, **init_kwargs)

        # If structured output requested, inject schema into the prompt
        if structured_output_format:
            schema = structured_output_format.get("json_schema", structured_output_format)
            prompt = (
                f"You must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\n"
                f"Respond only with parseable JSON and nothing else.\n\n"
                f"User query:\n{prompt}"
            )

        gen_config = GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        self.logger.info(
            "Querying Vertex AI model",
            extra={"model": model_name, "project": self.authentication_config.project_id},
        )

        response = gemini.generate_content(
            prompt,
            generation_config=gen_config,
        )

        content = response.text

        # Try to parse JSON if structured output was requested
        if structured_output_format:
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                self.logger.warning("Vertex AI response was not valid JSON despite structured output request")

        return {"response": content}


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="keeptest",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Vertex AI Provider",
        authentication={
            "project_id": os.environ.get("GCP_PROJECT_ID", "my-project"),
            "location": os.environ.get("GCP_LOCATION", "us-central1"),
            "credentials_json": os.environ.get("GOOGLE_CREDENTIALS_JSON", ""),
        },
    )
    provider = VertexAiProvider(
        context_manager=context_manager,
        provider_id="vertex-ai-test",
        config=config,
    )
    result = provider.query(
        prompt="Summarize this alert: CPU usage exceeded 95% for 5 minutes on prod-server-01.",
        model="gemini-1.5-flash-001",
        max_tokens=256,
        structured_output_format={
            "json_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "recommended_action": {"type": "string"},
                },
                "required": ["summary", "severity", "recommended_action"],
            }
        },
    )
    print(result)
