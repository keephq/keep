\"\"\"
OpensupportsProvider is a class that implements the BaseProvider interface for OpenSupports.
\"\"\"

import dataclasses
import json
import logging
from typing import List, Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class OpensupportsProviderAuthConfig:
    \"\"\"OpenSupports authentication configuration.\"\"\"

    host: str = dataclasses.field(
        metadata={
            \"required\": True,
            \"description\": \"OpenSupports Host URL\",
            \"hint\": \"https://opensupports.example.com\",
        }
    )
    email: str = dataclasses.field(
        metadata={
            \"required\": True,
            \"description\": \"OpenSupports Email\",
            \"sensitive\": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            \"required\": True,
            \"description\": \"OpenSupports Password\",
            \"sensitive\": True,
        }
    )


class OpensupportsProvider(BaseProvider):
    \"\"\"Push alerts to OpenSupports as tickets.\"\"\"

    PROVIDER_DISPLAY_NAME = \"OpenSupports\"
    PROVIDER_CATEGORY = [\"Ticketing\"]
    PROVIDER_TAGS = [\"ticketing\"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name=\"authenticated\",
            description=\"Authenticated with OpenSupports\",
            mandatory=True,
            alias=\"Authenticated\",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._token = None

    def validate_config(self):
        self.authentication_config = OpensupportsProviderAuthConfig(
            **self.config.authentication
        )

    def _login(self):
        if self._token:
            return self._token

        url = f\"{self.authentication_config.host.rstrip('/')}/api/system/login\"
        payload = {
            \"email\": self.authentication_config.email,
            \"password\": self.authentication_config.password,
        }
        response = requests.post(url, data=payload, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get(\"status\") == \"success\":
            self._token = data.get(\"data\", {}).get(\"token\")
            return self._token
        else:
            raise ProviderException(f\"Failed to login to OpenSupports: {data.get('message')}\")

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            self._login()
            return {\"authenticated\": True}
        except Exception as e:
            return {\"authenticated\": str(e)}

    def _notify(
        self,
        subject: str,
        content: str,
        department_id: str = \"1\",
        priority_id: str = \"1\",
        **kwargs,
    ):
        \"\"\"
        Create a ticket in OpenSupports.
        \"\"\"
        token = self._login()
        url = f\"{self.authentication_config.host.rstrip('/')}/api/ticket/create\"
        
        payload = {
            \"token\": token,
            \"subject\": subject,
            \"content\": content,
            \"departmentId\": department_id,
            \"priorityId\": priority_id,
        }
        
        # Merge with other optional parameters if provided
        payload.update(kwargs)

        response = requests.post(url, data=payload, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get(\"status\") == \"success\":
            ticket_id = data.get(\"data\", {}).get(\"ticketId\")
            return {
                \"ticket_id\": ticket_id,
                \"ticket_url\": f\"{self.authentication_config.host.rstrip('/')}/ticket/{ticket_id}\",
            }
        else:
            raise ProviderException(f\"Failed to create ticket in OpenSupports: {data.get('message')}\")

    def dispose(self):
        pass
