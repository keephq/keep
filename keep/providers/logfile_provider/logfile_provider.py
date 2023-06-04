"""
LogfileProvider is a class that implements the BaseOutputProvider interface for Mock messages.
"""
import datetime
import io
import os
import re
import uuid

import datefinder
from logmine_pkg.log_mine import LogMine

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class LogfileProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        pass

    def _query(self, **kwargs):
        """This is mock provider that just return the command output.

        Returns:
            _type_: _description_
        """

        filename = kwargs.get("filename")
        date = kwargs.get("time")

        seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

        def convert_to_seconds(s):
            return int(s[:-1]) * seconds_per_unit[s[-1]]

        seconds = convert_to_seconds(date)

        try:
            with open(filename, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            self.logger.exception(f"File {filename} not found")
            raise ProviderConfigException(
                f"File {filename} not found", provider_id=self.provider_id
            )

        relevant_lines = []
        for l in lines:
            # try the first one
            date = list(datefinder.find_dates(l))[0]
            if date + datetime.timedelta(seconds=seconds) > datetime.datetime.now():
                relevant_lines.append(l)

        tmp_filename = str(uuid.uuid4())
        with open(tmp_filename, "w") as f:
            f.writelines(relevant_lines)
        # TODO: make this configurable
        options = {
            "file": ["-"],
            "max_dist": 0.2,
            "variables": [],
            "delimeters": "\\s+",
            "min_members": 2,
            "k1": 1,
            "k2": 1,
            "sorted": "desc",
            "number_align": True,
            "pattern_placeholder": None,
            "highlight_patterns": False,
            "mask_variables": True,
            "highlight_variables": False,
            "single_core": False,
        }
        logmine = LogMine(
            # Processor config
            {k: options[k] for k in ("single_core",)},
            # Cluster config
            {
                k: options[k]
                for k in (
                    "max_dist",
                    "variables",
                    "delimeters",
                    "min_members",
                    "k1",
                    "k2",
                )
            },
            # Output config
            {
                k: options[k]
                for k in (
                    "sorted",
                    "number_align",
                    "pattern_placeholder",
                    "mask_variables",
                    "highlight_patterns",
                    "highlight_variables",
                )
            },
        )
        try:
            buffer = io.StringIO()
            logmine.output.set_output_file(file=buffer)
            logmine.run(files=[tmp_filename])
            buffer.seek(0)
            output = buffer.readlines()
        except Exception as e:
            self.logger.exception(f"Error while running logmine: {e}")
            raise ProviderConfigException(f"Error while running logmine: {e}", p)
        finally:
            os.unlink(tmp_filename)
        output = [self._remove_ansi(o).replace("\n", "") for o in output]
        return output

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _remove_ansi(self, text):
        ansi_escape = re.compile(
            r"""
            \x1B  # ESC
            (?:   # 7-bit C1 Fe (except CSI)
                [@-Z\\-_]
            |     # or [ for CSI, followed by a control sequence
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        """,
            re.VERBOSE,
        )
        result = ansi_escape.sub("", text)
        return result
