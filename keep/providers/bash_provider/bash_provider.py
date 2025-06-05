"""
BashProvider is a class that implements the BaseOutputProvider.
"""

import shlex
import subprocess

from keep.iohandler.iohandler import MustacheIOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class BashProvider(BaseProvider):
    """Enrich alerts with data using Bash."""

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.io_handler = MustacheIOHandler(context_manager=context_manager)

    def validate_config(self):
        pass

    def _query(
        self, timeout: int = 60, command: str = "", shell: bool = False, **kwargs
    ):
        """Bash provider eval shell command to get results

        Returns:
            _type_: _description_
        """
        parsed_command = self.io_handler.parse(command)

        if shell:
            # Use shell=True for complex commands
            try:
                result = subprocess.run(
                    parsed_command,
                    shell=True,
                    capture_output=True,
                    timeout=timeout,
                    text=True,
                )
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                }
            except subprocess.TimeoutExpired:
                try:
                    self.logger.warning(
                        "TimeoutExpired, using check_output - MacOS bug?"
                    )
                    stdout = subprocess.check_output(
                        parsed_command,
                        stderr=subprocess.STDOUT,
                        timeout=timeout,
                        shell=True,
                    ).decode()
                    return {
                        "stdout": stdout,
                        "stderr": None,
                        "return_code": 0,
                    }
                except Exception as e:
                    return {
                        "stdout": None,
                        "stderr": str(e),
                        "return_code": -1,
                    }
        else:
            # Original logic for simple commands
            parsed_commands = parsed_command.split("|")
            input_stream = None
            processes = []

            for cmd in parsed_commands:
                cmd_args = shlex.split(cmd.strip())
                process = subprocess.Popen(
                    cmd_args,
                    stdin=input_stream,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                if input_stream is not None:
                    input_stream.close()

                input_stream = process.stdout
                processes.append(process)

            try:
                stdout, stderr = processes[-1].communicate(timeout=timeout)
                return_code = processes[-1].returncode

                if stdout or stdout == b"":
                    stdout = stdout.decode()
                if stderr or stderr == b"":
                    stderr = stderr.decode()
            except subprocess.TimeoutExpired:
                try:
                    self.logger.warning(
                        "TimeoutExpired, using check_output - MacOS bug?"
                    )
                    stdout = subprocess.check_output(
                        parsed_command,
                        stderr=subprocess.STDOUT,
                        timeout=timeout,
                        shell=True,
                    ).decode()
                    stderr = None
                    return_code = 0
                except Exception as e:
                    stdout = None
                    stderr = str(e)
                    return_code = -1

            return {
                "stdout": str(stdout),
                "stderr": str(stderr),
                "return_code": return_code,
            }

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass
