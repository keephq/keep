import dataclasses
import typing
import pydantic

from keep.providers.base.base_provider import BaseProvider
from keep.contextmanager.contextmanager import ContextManager


@pydantic.dataclasses.dataclass
class AwsIncidenceProviderAuthConfig:
    aws_access_key_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS Access Key ID",
            "sensitive": True,
        }
    )

    aws_secret_access_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS Secret Access Key",
            "sensitive": True
        }
    )

    region_name: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS Region Name",
        }
    )



class AWSIncidencemanagerProvider(BaseProvider):
    def __init__(
        self, contextmanager=ContextManager
    )