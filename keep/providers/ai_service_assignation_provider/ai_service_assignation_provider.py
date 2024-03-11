import typing
import pydantic

from keep.iohandler.iohandler import IOHandler
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base_ai_provider.base_ai_provider import BaseAiProvider, BaseAiProviderAuthConfig
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class AiServiceAssignationProviderAuthConfig(BaseAiProviderAuthConfig):
    pass

class ServiceDescription(pydantic.BaseModel):
    service: str
    description: str

class AiServiceAssignationProvider(BaseAiProvider):
    """
    This provider will assign a "service" to the alert based on the alert name.
    """

    PROVIDER_DISPLAY_NAME = "AI Service Assignation Provider"
    provider_description = "AI Provider will enrich payload with service name."

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.io_handler = IOHandler(context_manager=context_manager)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = AiServiceAssignationProviderAuthConfig(
            **self.config.authentication
        )
    
    def _query(self, services_and_descriptions, **kwargs):
        try:
            services_and_descriptions = pydantic.parse_obj_as(
                typing.List[ServiceDescription], services_and_descriptions
            )
        except pydantic.ValidationError:
            raise ValueError(
                    """services_and_descriptions must be a list of ServiceDescription 
                    objects like [{'service': 'service_name', 'description': 'service_description'}]"""
                )

        prompt = "; ".join(
            [f"Service: \"{service.service}\" ({service.description})" for service in services_and_descriptions]
        )
        prompt += " Assign only one service, choose between: " 
        prompt += ", ".join(
            [service.service for service in services_and_descriptions]
        ) 

        template = {
            "service": "|".join([str(k) for k in [service.service for service in services_and_descriptions]]),
        }
        alert = self.context_manager.get_full_context()['alert']
        enrichment = self._execute_model(
            template=template, 
            instruction=prompt, 
            alert=alert.name,
            as_enrichment=True
        )
        return {"enrich_alert": enrichment}


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[
                        logging.StreamHandler()])

    # Load environment variables
    import os

    host = os.environ.get("OLLAMA_HOST")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = {
        "authentication": {"host": host}
    }
    provider: AiServiceAssignationProvider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="ai-service-assignation-provider-id",
        provider_type="ai-service-assignation-provider",
        provider_config=config,
    )
