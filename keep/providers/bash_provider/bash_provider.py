"""
BashProvider is a class that implements the BaseOutputProvider.
"""
import subprocess

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class BashProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.io_handler = IOHandler()

    def validate_config(self):
        pass

    def query(self, **kwargs):
        """Bash provider eval shell command to get results

        Returns:
            _type_: _description_
        """
        command = kwargs.get("command", "")
        parsed_command = self.io_handler.parse(command)
        try:
            output = subprocess.run(parsed_command, shell=True, stdout=subprocess.PIPE)
        except Exception as e:
            return {"status_code": "500", "output": str(e)}

        try:
            stdout = output.stdout.decode()
        except:
            stdout = ""

        try:
            stderr = output.stderr.decode()
        except:
            stderr = ""
        return {"stdout": stdout, "stderr": stderr, "exit_code": output.returncode}

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
