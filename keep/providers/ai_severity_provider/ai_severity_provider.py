from keep.iohandler.iohandler import IOHandler
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base_ai_provider.base_ai_provider import BaseAiProvider, BaseAiProviderAuthConfig
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class AiSeverityProviderAuthConfig(BaseAiProviderAuthConfig):
    pass

class AiSeverityProvider(BaseAiProvider):
    """
    Provider will enrich alert with severity based on the free-text instruction.
    """

    PROVIDER_DISPLAY_NAME = "AI Provider"
    provider_description = "AI Provider will enrich payload with missing fields."

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.io_handler = IOHandler(context_manager=context_manager)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        self.authentication_config = AiSeverityProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, severity_instruction, **kwargs):
        template = {
            "severity": "info|critical",
        }
        alert = self.context_manager.get_full_context()['alert']
        enrichment = self._execute_model(
            template=template, 
            instruction=severity_instruction, 
            alert=alert.name,
            as_enrichment=True,
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
    provider: AiSeverityProvider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="ai-severity-provider-id",
        provider_type="ai-severity-provider",
        provider_config=config,
    )
