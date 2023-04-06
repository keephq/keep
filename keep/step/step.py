import logging
from dataclasses import field

import chevron
from pydantic.dataclasses import dataclass

from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


@dataclass(config={"arbitrary_types_allowed": True})
class Step:
    step_id: str
    step_config: dict
    provider: BaseProvider
    provider_parameters: dict

    def __post_init__(self):
        self.io_handler = IOHandler()
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager.get_instance()

    @property
    def foreach(self):
        return self.step_config.get("foreach")

    def run(self):
        try:
            # Inject the context to the parameters
            for parameter in self.provider_parameters:
                self.provider_parameters[parameter] = self.io_handler.render(
                    self.provider_parameters[parameter]
                )
            step_output = self.provider.query(**self.provider_parameters)
            self.context_manager.set_step_context(self.step_id, results=step_output)
        except Exception as e:
            raise StepError(e)

        return step_output


class StepError(Exception):
    pass
