"""
BedrockProvider is a class that provides a way to interact with AWS Bedrock
foundational models (Claude, Llama, Titan, Mistral, etc.) for AI-powered workflows.
"""

import dataclasses
import json
import logging

import boto3
import pydantic
from botocore.exceptions import BotoCoreError, ClientError

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BedrockProviderAuthConfig:
    """AWS Bedrock authentication configuration."""

    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region where Bedrock is available (e.g. us-east-1)",
            "sensitive": False,
            "hint": "e.g. us-east-1",
        }
    )

    access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS access key ID (leave empty to use IAM role / instance profile)",
            "sensitive": True,
        },
    )

    secret_access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS secret access key (leave empty to use IAM role / instance profile)",
            "sensitive": True,
        },
    )

    session_token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS session token (required only for temporary credentials)",
            "sensitive": True,
        },
    )


class BedrockProvider(BaseProvider):
    """Interact with AWS Bedrock foundational models."""

    PROVIDER_DISPLAY_NAME = "AWS Bedrock"
    PROVIDER_CATEGORY = ["AI"]

    # Default model — Amazon Titan for backwards compat; callers can override
    DEFAULT_MODEL = "amazon.titan-text-express-v1"

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._client = None

    def validate_config(self):
        self.authentication_config = BedrockProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return (or lazily create) a boto3 bedrock-runtime client."""
        if self._client is not None:
            return self._client

        kwargs = {"region_name": self.authentication_config.region}

        if self.authentication_config.access_key:
            kwargs["aws_access_key_id"] = self.authentication_config.access_key
        if self.authentication_config.secret_access_key:
            kwargs["aws_secret_access_key"] = self.authentication_config.secret_access_key
        if self.authentication_config.session_token:
            kwargs["aws_session_token"] = self.authentication_config.session_token

        self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def _build_request_body(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        structured_output_format: dict | None,
    ) -> str:
        """Build a model-specific request body for InvokeModel."""
        model_lower = model_id.lower()

        # Claude models (via Bedrock Messages API)
        if "anthropic.claude" in model_lower:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if structured_output_format:
                schema = structured_output_format.get("json_schema", {})
                body["system"] = (
                    f"You must respond with valid JSON matching this schema: "
                    f"{json.dumps(schema)}\nRespond with JSON only."
                )
            return json.dumps(body)

        # Meta Llama models
        if "meta.llama" in model_lower:
            body = {"prompt": prompt, "max_gen_len": max_tokens}
            return json.dumps(body)

        # Mistral models
        if "mistral" in model_lower:
            body = {
                "prompt": f"<s>[INST]{prompt}[/INST]",
                "max_tokens": max_tokens,
            }
            return json.dumps(body)

        # Cohere Command models
        if "cohere.command" in model_lower:
            body = {"prompt": prompt, "max_tokens": max_tokens}
            return json.dumps(body)

        # Amazon Titan models (default)
        body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": 0.0,
            },
        }
        return json.dumps(body)

    def _parse_response(self, model_id: str, raw: dict) -> str:
        """Extract text content from the model-specific response structure."""
        model_lower = model_id.lower()

        if "anthropic.claude" in model_lower:
            return raw.get("content", [{}])[0].get("text", "")

        if "meta.llama" in model_lower:
            return raw.get("generation", "")

        if "mistral" in model_lower:
            outputs = raw.get("outputs", [{}])
            return outputs[0].get("text", "") if outputs else ""

        if "cohere.command" in model_lower:
            generations = raw.get("generations", [{}])
            return generations[0].get("text", "") if generations else ""

        # Amazon Titan
        results = raw.get("results", [{}])
        return results[0].get("outputText", "") if results else ""

    # ------------------------------------------------------------------
    # Public query interface
    # ------------------------------------------------------------------

    def _query(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        structured_output_format: dict | None = None,
    ) -> dict:
        """
        Send a prompt to an AWS Bedrock foundational model.

        Args:
            prompt: The text prompt.
            model: Bedrock model ID (e.g. 'anthropic.claude-3-sonnet-20240229-v1:0').
                   Defaults to amazon.titan-text-express-v1.
            max_tokens: Maximum tokens to generate.
            structured_output_format: Optional JSON schema dict (same format as OpenAI).

        Returns:
            dict with 'response' key containing the model's reply.
        """
        model_id = model or self.DEFAULT_MODEL
        client = self._get_client()

        body = self._build_request_body(model_id, prompt, max_tokens, structured_output_format)

        try:
            response = client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            raise ProviderException(
                f"AWS Bedrock ClientError [{error_code}]: {e.response['Error']['Message']}"
            )
        except BotoCoreError as e:
            raise ProviderException(f"AWS Bedrock error: {str(e)}")

        raw = json.loads(response["body"].read())
        text = self._parse_response(model_id, raw)

        # Try to parse as JSON if structured output was requested
        if structured_output_format:
            try:
                text = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                pass

        return {"response": text}


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="AWS Bedrock Provider",
        authentication={
            "region": os.environ.get("AWS_REGION", "us-east-1"),
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        },
    )

    provider = BedrockProvider(
        context_manager=context_manager,
        provider_id="bedrock_provider",
        config=config,
    )

    # Test with Titan (no AWS credentials needed for schema validation)
    print(
        provider.query(
            prompt="Classify this alert environment: Clients are panicking, nothing works.",
            model="anthropic.claude-3-haiku-20240307-v1:0",
            structured_output_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "environment_classification",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "environment": {
                                "type": "string",
                                "enum": ["production", "staging", "development"],
                            }
                        },
                        "required": ["environment"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            max_tokens=100,
        )
    )
