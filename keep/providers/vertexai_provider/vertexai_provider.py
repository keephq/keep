"""
Vertex AI Provider for Google Cloud Platform LLM integration.
"""

import dataclasses
import json
import os
from typing import Optional

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VertexaiProviderAuthConfig:
    """
    Vertex AI authentication configuration.
    Supports service account JSON or workload identity.
    """

    service_account_json: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Google Cloud service account JSON key. If not provided, will use workload identity or application default credentials.",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": "application/json",
        },
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google Cloud project ID where Vertex AI is enabled",
        },
    )
    location: str = dataclasses.field(
        default="us-central1",
        metadata={
            "required": False,
            "description": "Google Cloud region for Vertex AI (e.g., us-central1, us-east1, europe-west1)",
        },
    )


class VertexaiProvider(BaseProvider):
    """
    Vertex AI Provider for accessing Google Cloud LLMs (Gemini, etc.) through Vertex AI.
    """

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_CATEGORY = ["AI", "Cloud Infrastructure"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.client = None

    def validate_config(self):
        """Validate Vertex AI configuration."""
        if self.config.authentication is None:
            self.config.authentication = {}
        
        # Try to get project_id from environment if not provided
        if "project_id" not in self.config.authentication or not self.config.authentication.get("project_id"):
            env_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
            if env_project:
                self.config.authentication["project_id"] = env_project
        
        self.authentication_config = VertexaiProviderAuthConfig(
            **self.config.authentication
        )

    def init_client(self):
        """Initialize Vertex AI client."""
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError:
            raise ImportError(
                "Google Cloud Vertex AI SDK not found. "
                "Install with: pip install google-cloud-aiplatform"
            )

        # Initialize Vertex AI
        if self.authentication_config.service_account_json:
            # Use service account JSON
            if isinstance(self.authentication_config.service_account_json, dict):
                credentials_info = self.authentication_config.service_account_json
            elif isinstance(self.authentication_config.service_account_json, str):
                try:
                    credentials_info = json.loads(self.authentication_config.service_account_json)
                except json.JSONDecodeError:
                    # It might be a file path, try to read it
                    with open(self.authentication_config.service_account_json, 'r') as f:
                        credentials_info = json.load(f)
            else:
                credentials_info = self.authentication_config.service_account_json

            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            
            vertexai.init(
                project=self.authentication_config.project_id,
                location=self.authentication_config.location,
                credentials=credentials,
            )
        else:
            # Use workload identity or application default credentials
            vertexai.init(
                project=self.authentication_config.project_id,
                location=self.authentication_config.location,
            )

        self.GenerativeModel = GenerativeModel

    def dispose(self):
        """Clean up resources."""
        self.client = None

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the provider can connect to Vertex AI."""
        scopes = {}
        try:
            self.init_client()
            # Try to list available models as a connectivity check
            model = self.GenerativeModel("gemini-1.5-flash-001")
            scopes["vertex_ai_connectivity"] = True
        except Exception as e:
            scopes["vertex_ai_connectivity"] = str(e)
        return scopes

    def _query(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash-001",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        structured_output_format: Optional[dict] = None,
    ):
        """
        Query Vertex AI LLM with the given prompt.

        Args:
            prompt (str): The user query/prompt.
            model (str): The Vertex AI model ID (e.g., gemini-1.5-flash-001, gemini-1.5-pro-001).
            max_tokens (int): Maximum number of tokens to generate.
            temperature (float): Sampling temperature (0.0 to 1.0).
            system_prompt (str): Optional system prompt/instructions.
            structured_output_format (dict): Optional JSON schema for structured output.

        Returns:
            dict: Response containing the generated text.
        """
        self.init_client()

        # Initialize the model
        generative_model = self.GenerativeModel(model)

        # Prepare generation config
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        # Prepare content
        contents = []
        if system_prompt:
            # For Gemini models, system prompt is handled differently
            # We'll prepend it to the user prompt for now
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Add structured output instructions if provided
        if structured_output_format:
            schema = structured_output_format.get("json_schema", {})
            json_instruction = (
                f"\n\nYou must respond with valid JSON that matches this schema: {json.dumps(schema)}\n"
                "Your response must be parseable JSON and nothing else."
            )
            full_prompt += json_instruction

        contents.append(full_prompt)

        # Generate response
        response = generative_model.generate_content(
            contents,
            generation_config=generation_config,
        )

        # Extract text from response
        text_response = response.text

        # Try to parse as JSON if structured output was requested
        if structured_output_format:
            try:
                text_response = json.loads(text_response)
            except json.JSONDecodeError:
                pass  # Return as string if not valid JSON

        return {
            "response": text_response,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else None,
            } if hasattr(response, 'usage_metadata') else None,
        }

    def notify(self, **kwargs):
        """Notification not supported for AI provider."""
        pass

    def get_alerts_configuration(self, alert_id: Optional[str] = None):
        """Not applicable for AI provider."""
        pass

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        """Not applicable for AI provider."""
        pass

    @staticmethod
    def get_alert_schema() -> dict:
        """Not applicable for AI provider."""
        return {}

    def get_logs(self, limit: int = 5) -> list:
        """Not applicable for AI provider."""
        return []

    def expose(self):
        """Expose provider capabilities."""
        return {
            "models": [
                "gemini-1.5-flash-001",
                "gemini-1.5-pro-001",
                "gemini-1.0-pro-001",
            ],
            "supported_operations": ["query"],
        }


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Test with environment credentials
    config = ProviderConfig(
        authentication={
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project"),
            "location": "us-central1",
        }
    )

    provider = VertexaiProvider(
        context_manager=context_manager,
        provider_id="vertexai-test",
        config=config,
    )

    # Test query
    result = provider._query(
        prompt="What is the capital of France?",
        model="gemini-1.5-flash-001",
    )
    print(result)
