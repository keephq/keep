import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from keep.api.core.db import get_provider_by_suffix_without_tenant_id
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


# Shahar: this is unauthorized endpoint because providers events are not authenticated
#         therefore - providers should authenticate the events themselves


@router.post("/{provider_type}")
async def handle_provider_events(
    provider_type: str,
    request: Request,
):
    """
    Generic endpoint to handle events from any provider type

    The provider_id can be passed as a query parameter or determined from the request
    """
    # Special case for Slack URL verification that doesn't require authentication
    provider_class = ProvidersFactory.get_provider_class(provider_type)

    # 1. Verify the request
    try:
        logger.info(f"Verifying {provider_type} request")
        await provider_class.verify_request(request)
        logger.info(f"Verified {provider_type} request")
    except Exception as e:
        logger.exception(f"Failed to verify {provider_type} request")
        return JSONResponse(status_code=400, content={"error": str(e)})

    # 2. Try to challenge the provider (if needed). Mostly for the installation process
    try:
        logger.info(f"Challenging {provider_type} request")
        challenge = await provider_class.challenge(request)
        if challenge:
            logger.info(f"Challenged {provider_type} request")
            return challenge
        # else, continue to the next step
    except ProviderException as e:
        logger.exception(f"Failed to challenge {provider_type} request")
        return JSONResponse(status_code=400, content={"error": str(e)})

    # 3. Parse the request payload
    try:
        raw_data = await request.json()
        logger.info(
            f"Received {provider_type} event with payload size: {len(str(raw_data))}"
        )
    except Exception:
        logger.exception("Failed to parse request JSON")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON payload"})
    # 3. Extract provider_id from the request
    try:
        provider_suffix = await provider_class.extract_provider_id_from_event(
            raw_data, request
        )
        # provider name should be unique - e.g. team id
        provider = get_provider_by_suffix_without_tenant_id(provider_suffix)
        tenant_id = provider.tenant_id
    except Exception:
        logger.exception("Failed to extract provider_id from event")
        return JSONResponse(
            status_code=400, content={"error": "Failed to extract provider_id"}
        )

    # 4. init the provider
    try:
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        provider_config = secret_manager.read_secret(
            provider.configuration_key, is_json=True
        )
        provider_instance = ProvidersFactory.get_provider(
            context_manager, provider.id, provider.type, provider_config
        )
    except Exception:
        logger.exception("Failed to initialize provider")
        return JSONResponse(
            status_code=500, content={"error": "Failed to initialize provider"}
        )

    # 5. handle the event
    try:
        await provider_instance.handle_event(raw_data)
        logger.info(f"Handled {provider_type} event")
    except Exception:
        logger.exception(f"Failed to handle {provider_type} event")
        return JSONResponse(
            status_code=500, content={"error": "Failed to handle event"}
        )
