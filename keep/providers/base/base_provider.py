# base_provider.py
from enum import Enum

class ProviderType(Enum):
    INCIDENT_MANAGEMENT = "incident_management"
    # Add other types as needed

class BaseProvider:
    def __init__(self, config):
        self.config = config

    @property
    def name(self):
        raise NotImplementedError

    @property
    def type(self):
        raise NotImplementedError
