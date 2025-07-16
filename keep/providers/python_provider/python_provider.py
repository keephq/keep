"""
PythonProvider is a class that implements the BaseOutputProvider.
"""

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.exceptions.provider_exception import ProviderException
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class PythonProvider(BaseProvider):
    """Python provider eval python code to get results"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.io_handler = IOHandler(context_manager=context_manager)

    def validate_config(self):
        pass

    def _query(self, code: str = "", imports: str = "", **kwargs):
        """Python provider eval python code to get results

        Returns:
            _type_: _description_
        """
        modules = imports
        loaded_modules = {}
        if modules:
            for module in modules.split(","):
                try:
                    imported_module = __import__(module, fromlist=[""])
                    # Add all public attributes from the module to loaded_modules
                    for attr_name in dir(imported_module):
                        if not attr_name.startswith("_"):
                            loaded_modules[attr_name] = getattr(
                                imported_module, attr_name
                            )
                    # Add the module itself too..
                    loaded_modules[module] = imported_module
                except Exception:
                    raise ProviderConfigException(
                        f"{self.__class__.__name__} failed to import library: {module}",
                        provider_id=self.provider_id,
                    )
        parsed_code = self.io_handler.parse(code)
        try:
            output = eval(parsed_code, loaded_modules)
        except Exception as e:
            raise ProviderException(e)
        return output

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    # Example usage
    # Output debug messages
    import logging

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    python_provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="python-keephq",
        provider_type="python",
        provider_config={"authentication": {}},
    )

    # Example query
    result = python_provider._query(code="1 + 1", imports="keep.api.models.alert")
    print(result)  # Output: 2
