import json
import ollama
import pydantic
import dataclasses

from threading import Lock

from keep.providers.base.base_provider import BaseProvider
from httpx import ConnectError


class OllamaLock:
    """
    Joint lock for all Ollama requests to prevent clogging and execution of requests after Keep restart.
    """

    lock = Lock()


@pydantic.dataclasses.dataclass
class BaseAiProviderAuthConfig:
    """
    Ai provider backend host.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "ollama host",
            "hint": "http://localhost:11434",
        },
    )


class BaseAiProvider(BaseProvider):
    """
    Base AI provider.
    Using Ollama only for now.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _execute_model(self, template, instruction, alert, as_enrichment=False):
        model_name = "mistral:7b-instruct-v0.2-q2_K"

        with OllamaLock.lock:
            # In case model is not present:
            try:
                ollama.Client(host=self.authentication_config.host).show(model_name)
            except ollama._types.ResponseError:
                self.logger.info(f"Pulling the missing model: {model_name}.")
                ollama.Client(host=self.authentication_config.host).pull(
                    model_name, host=self.authentication_config.host
                )
            except ConnectError:
                self.logger.error(
                    "Failed to connect to Ollama. Please check Ollama host."
                )
                return {}

            self.logger.info(
                f"Executing model: {model_name} with instruction: {instruction} and alert {alert}."
            )
            response = ollama.Client(host=self.authentication_config.host).generate(
                model=model_name,
                format="json",
                options={
                    "num_predict": 128,  # If response is {}, increase this value. May make generaton slower.
                },
                prompt="Respond using JSON. Key names should have no backslashes, values should use plain ascii with no special characters. "
                + str(instruction)
                + " Alert: "
                + str(alert)
                + f"\nUse the following template: {str(json.dumps(template))}.",
            )
            self.logger.info(
                f"Finished executing model {model_name} with instruction {instruction} and alert {alert}, response: {response['response']}."
            )
        try:
            json_response = json.loads(response["response"])
            if as_enrichment:
                if len(json_response) != 1:
                    self.logger.info(
                        f"Alert could be enriched with only one field, but: {json_response} was given."
                    )
                    return {}
                list_from_dict = [(k, v) for k, v in json_response.items()][0]
                enrichments = {"key": list_from_dict[0], "value": list_from_dict[1]}
                return enrichments
            else:
                return json_response
        except Exception as e:
            self.logger.debug(f"Failed to parse response: {e}")
            self.logger.info(f"AI gave unparsable response: {response['response']}")
            return {}
