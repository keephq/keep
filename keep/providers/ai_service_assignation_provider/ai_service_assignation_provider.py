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

        query = "; ".join(
            [f"Service: \"{service.service}\" ({service.description})" for service in services_and_descriptions]
        )
        query += " Assign only one service, choose between: " 
        query += ", ".join(
            [service.service for service in services_and_descriptions]
        ) 

        template = {
            "service": "|".join([str(k) for k in [service.service for service in services_and_descriptions]]),
            "reason": "string describing why exactly this service was chosen",
        }
        alert = self.context_manager.get_full_context()['alert']
        labels = self._execute_model(
            template=template, 
            instruction=query, 
            alert=alert.name
        )
        return labels


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
