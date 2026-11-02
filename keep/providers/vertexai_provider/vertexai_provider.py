"""
Vertex AI Provider is a class that provides a way to query Google Cloud Vertex AI models.

Vertex AI is Google Cloud's unified ML platform that provides access to foundation models
including Gemini, Claude (via Model Garden), and other LLMs through a unified API.
"""

import dataclasses
import json
import logging

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class VertexaiProviderAuthConfig:
    """Vertex AI authentication configuration.

    Supports two authentication methods:
    1. API key (for Google AI Studio / Vertex AI in express mode)
    2. Service account JSON (for full Vertex AI with project/region)
    """

    # Option 1: API key authentication (simpler, for AI Studio / express mode)
    api_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Google AI/Vertex AI API Key (for express mode)",
            "sensitive": True,
        },
        default=None,
    )

    # Option 2: Service account authentication (for full Vertex AI)
    service_account_json: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Google Cloud service account JSON key (base64 encoded or raw JSON)",
            "sensitive": True,
        },
        default=None,
    )

    project_id: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Google Cloud project ID (required for service account auth)",
            "sensitive": False,
        },
        default=None,
    )

    region: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Google Cloud region for Vertex AI",
            "sensitive": False,
            "type": "select",
            "options": [
                "us-central1",
                "us-east1",
                "us-east4",
                "us-west1",
                "europe-west1",
                "europe-west2",
                "europe-west3",
                "europe-west4",
                "asia-east1",
                "asia-northeast1",
                "asia-southeast1",
            ],
        },
        default="us-central1",
    )


class VertexaiProvider(BaseProvider):
    """Query Google Cloud Vertex AI foundation models.

    Vertex AI provides access to Google's foundation models (Gemini, etc.)
    for text generation, structured output, and AI-powered workflows within Keep.
    """

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_CATEGORY = ["AI"]
    PROVIDER_TAGS = ["data"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate the authentication configuration.

        Requires either an API key or a service account JSON with project ID.
        """
        self.authentication_config = VertexaiProviderAuthConfig(
            **self.config.authentication
        )

        if not self.authentication_config.api_key and not self.authentication_config.service_account_json:
            raise ValueError(
                "Either 'api_key' or 'service_account_json' must be provided for Vertex AI authentication"
            )

        if self.authentication_config.service_account_json and not self.authentication_config.project_id:
            raise ValueError(
                "'project_id' is required when using service account authentication"
            )

    def dispose(self):
        """Dispose of the provider. No cleanup needed."""
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate the provider scopes/permissions."""
        scopes = {}
        try:
            # Try a minimal request to validate credentials
            self._query(prompt="test", max_tokens=1)
            scopes["vertex_ai_access"] = True
        except Exception as e:
            scopes["vertex_ai_access"] = str(e)
        return scopes

    def _get_client(self):
        """Get the appropriate Vertex AI client based on auth method.

        Returns:
            A configured generative model client.
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required. "
                "Install it with: pip install google-generativeai"
            )

        if self.authentication_config.api_key:
            # API key mode (Google AI Studio / Vertex AI express)
            genai.configure(api_key=self.authentication_config.api_key)
            return genai
        else:
            # Service account mode (full Vertex AI)
            # For service account, we use the vertexai SDK if available,
            # otherwise fall back to google-generativeai with ADC
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel

                sa_json = self.authentication_config.service_account_json
                project = self.authentication_config.project_id
                region = self.authentication_config.region

                # Write service account to temp file for ADC
                import os
                import tempfile

                try:
                    sa_data = json.loads(sa_json)
                except (json.JSONDecodeError, TypeError):
                    # Might be base64 encoded
                    import base64

                    sa_data = json.loads(
                        base64.b64decode(sa_json).decode("utf-8")
                    )

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                ) as f:
                    json.dump(sa_data, f)
                    sa_path = f.name

                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
                vertexai.init(project=project, location=region)

                return {
                    "mode": "vertexai",
                    "module": vertexai,
                    "GenerativeModel": GenerativeModel,
                    "sa_path": sa_path,
                }
            except ImportError:
                # Fall back to google-generativeai with ADC
                import google.auth
                import google.auth.credentials

                sa_json_str = self.authentication_config.service_account_json
                try:
                    sa_data = json.loads(sa_json_str)
                except (json.JSONDecodeError, TypeError):
                    import base64

                    sa_data = json.loads(
                        base64.b64decode(sa_json_str).decode("utf-8")
                    )

                credentials, project = google.auth.load_credentials_from_dict(
                    sa_data,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                genai.configure(credentials=credentials)
                return genai

    def _query(
        self,
        prompt: str,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 1024,
        structured_output_format: dict | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """Query a Vertex AI model with the given prompt.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use (default: gemini-2.0-flash).
                Common options: gemini-2.0-flash, gemini-2.0-flash-lite,
                gemini-1.5-pro, gemini-1.5-flash
            max_tokens: Maximum number of tokens to generate.
            structured_output_format: Optional JSON schema for structured output.
            temperature: Sampling temperature (0.0 - 1.0).

        Returns:
            dict: Response containing the model output.
        """
        client_result = self._get_client()

        # Handle structured output
        system_instruction = None
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            system_instruction = (
                f"You must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else."
            )

        if isinstance(client_result, dict) and client_result.get("mode") == "vertexai":
            # Full Vertex AI SDK mode
            GenerativeModel = client_result["GenerativeModel"]
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }

            model_instance = GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
            )
            response = model_instance.generate_content(
                prompt,
                generation_config=generation_config,
            )
            content = response.text
        else:
            # google-generativeai mode (API key or ADC)
            genai = client_result
            model_instance = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
            )
            response = model_instance.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                ),
            )
            content = response.text

        # Try to parse as JSON if structured output was requested
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        return {
            "response": content,
        }


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Test with API key
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("VERTEX_AI_API_KEY")

    if api_key:
        config = ProviderConfig(
            description="Vertex AI Provider",
            authentication={
                "api_key": api_key,
            },
        )

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=config,
        )

        result = provider.query(
            prompt="What is 2+2? Answer with just the number.",
            model="gemini-2.0-flash",
            max_tokens=10,
        )
        print(f"Query result: {result}")
    else:
        print("Set GOOGLE_API_KEY or VERTEX_AI_API_KEY to test the provider")
