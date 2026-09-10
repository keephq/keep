import json
import dataclasses

import boto3
import pydantic
from botocore.exceptions import ClientError, BotoCoreError

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BedrockProviderAuthConfig:
    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region (e.g. us-east-1)",
            "sensitive": False,
            "hint": "e.g. us-east-1",
        },
    )
    access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS access key (leave empty for IAM role)",
            "sensitive": True,
        },
    )
    secret_access_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS secret access key (leave empty for IAM role)",
            "sensitive": True,
        },
    )


class BedrockProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "AWS Bedrock"
    PROVIDER_CATEGORY = ["AI"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
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

    def _get_client(self):
        if self._client is not None:
            return self._client

        kwargs = {"region_name": self.authentication_config.region}
        if self.authentication_config.access_key:
            kwargs["aws_access_key_id"] = self.authentication_config.access_key
        if self.authentication_config.secret_access_key:
            kwargs["aws_secret_access_key"] = self.authentication_config.secret_access_key

        self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def _query(
        self,
        prompt: str,
        model: str = "anthropic.claude-3-haiku-20240307-v1:0",
        max_tokens: int = 1024,
        structured_output_format: dict | None = None,
    ) -> dict:
        client = self._get_client()
        model_id = model

        # Build request body based on model family
        if "anthropic.claude" in model_id:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if structured_output_format:
                schema = structured_output_format.get("json_schema", {})
                body["system"] = (
                    f"Respond with valid JSON matching this schema: "
                    f"{json.dumps(schema)}"
                )
        elif "meta.llama" in model_id:
            body = {"prompt": prompt, "max_gen_len": max_tokens}
        elif "mistral" in model_id:
            body = {"prompt": f"<s>[INST]{prompt}[/INST]", "max_tokens": max_tokens}
        elif "cohere.command" in model_id:
            body = {"prompt": prompt, "max_tokens": max_tokens}
        else:
            # Amazon Titan and other models
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": 0.0,
                },
            }

        try:
            response = client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
        except ClientError as e:
            raise ProviderException(
                f"Bedrock error [{e.response['Error']['Code']}]: "
                f"{e.response['Error']['Message']}"
            )
        except BotoCoreError as e:
            raise ProviderException(f"Bedrock error: {str(e)}")

        raw = json.loads(response["body"].read())

        # Parse response based on model family
        if "anthropic.claude" in model_id:
            text = raw.get("content", [{}])[0].get("text", "")
        elif "meta.llama" in model_id:
            text = raw.get("generation", "")
        elif "mistral" in model_id:
            text = raw.get("outputs", [{}])[0].get("text", "")
        elif "cohere.command" in model_id:
            text = raw.get("generations", [{}])[0].get("text", "")
        else:
            text = raw.get("results", [{}])[0].get("outputText", "")

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

    print(
        provider.query(
            prompt="Classify this alert: Clients are panicking, nothing works.",
            model="anthropic.claude-3-haiku-20240307-v1:0",
        )
    )
