"""
LogfileProvider is a class that implements the BaseOutputProvider interface for Mock messages.
"""


from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class PythonProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.io_handler = IOHandler()

    def validate_config(self):
        pass

    def query(self, **kwargs):
        """Python provider eval python code to get results

        Returns:
            _type_: _description_
        """
        code = kwargs.pop("code", "")
        libraries = kwargs.pop("libraries", "")
        for library in libraries.split(","):
            try:
                __import__(library)
            except Exception as e:
                raise ProviderConfigException(
                    f"{self.__class__.__name__} failed to import library: {library}"
                )
        parsed_code = self.io_handler.parse(code)
        output = eval(parsed_code)
        return output

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
