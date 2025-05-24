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
            self,
            timeout: int = 60,
            command: str = "",
            **kwargs
            ):
        """Bash provider eval shell command to get results

        Returns:
            _type_: _description_
        """
        # timeout = kwargs.get("timeout", 60)
        # command = kwargs.get("command", "")
        parsed_command = self.io_handler.parse(command)
        # parse by pipes
        parsed_commands = parsed_command.split("|")
        # Initialize the input for the first command
        input_stream = None

        processes = []

        for cmd in parsed_commands:
            # Split the command string into a list of arguments
            cmd_args = shlex.split(cmd.strip())

            # Run the command and pipe its output to the next command, capturing stderr
            process = subprocess.Popen(
                cmd_args,
                stdin=input_stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if input_stream is not None:
                # Close the input_stream (output of the previous command)
                input_stream.close()

            # Update input_stream to be the output of the current command
            input_stream = process.stdout

            # Append the current process to the list of processes
            processes.append(process)

        # Get the final output
        try:
            stdout, stderr = processes[-1].communicate(timeout=timeout)
            return_code = processes[-1].returncode
            # stdout and stderr are strings or None
            if stdout or stdout == b"":
                stdout = stdout.decode()

            if stderr or stderr == b"":
                stderr = stderr.decode()
        except subprocess.TimeoutExpired:
            # use check_output to get the output of the last process
            # this is some MacOS bug, where communicate() doesn't work and raise TimeoutExpired (idk why but it works on Linux)
            try:
                self.logger.warning("TimeoutExpired, using check_output - MacOS bug?")
                stdout = subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, timeout=timeout, shell=True
                ).decode()
                stderr = None
                return_code = 0
                self.logger.warning("check_output worked")
            # todo: fix that
            except Exception as e:
                stdout = None
                stderr = e.args[1].decode()
                return_code = e.args[0]

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
