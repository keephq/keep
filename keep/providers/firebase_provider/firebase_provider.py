"""Firebase backend platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FirebaseProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Firebase API Key", "sensitive": True},
        default=""
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "Firebase Project ID"},
        default=""
    )

class FirebaseProvider(BaseProvider):
    """Firebase backend platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Firebase"
    PROVIDER_CATEGORY = ["Backend"]
    FIREBASE_API = "https://firestore.googleapis.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.FIREBASE_API}/projects/{self.authentication_config.project_id}/databases/(default)/documents"

    def validate_config(self):
        self.authentication_config = FirebaseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, collection: str = "", document_id: str = "", fields: dict = None, **kwargs: Dict[str, Any]):
        if not collection or not document_id:
            raise ProviderException("Collection and document ID are required")

        # Convert fields to Firestore format
        firestore_fields = {}
        for key, value in (fields or {}).items():
            firestore_fields[key] = {"stringValue": str(value)}

        payload = {
            "fields": firestore_fields
        }

        try:
            response = requests.patch(
                f"{self.api_url}/{collection}/{document_id}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Firebase API error: {e}")

        self.logger.info(f"Firebase document created: {collection}/{document_id}")
        return {"status": "success", "collection": collection, "document_id": document_id}
