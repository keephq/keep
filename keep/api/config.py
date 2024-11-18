import logging
import os

import keep.api.logging
from keep.api.api import AUTH_TYPE
from keep.api.core.db_on_start import migrate_db, try_create_single_tenant
from keep.api.core.report_uptime import launch_uptime_reporting
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.identitymanagerfactory import IdentityManagerTypes

PORT = int(os.environ.get("PORT", 8080))

keep.api.logging.setup_logging()
logger = logging.getLogger(__name__)

LIVE_DEMO_MODE = os.environ.get("KEEP_LIVE_DEMO_MODE", "false").lower() == "true"


def on_starting(server=None):
    """This function is called by the gunicorn server when it starts"""
    logger.info("Keep server starting")

    migrate_db()
    launch_uptime_reporting()

    # Create single tenant if it doesn't exist
    if AUTH_TYPE in [
        IdentityManagerTypes.DB.value,
        IdentityManagerTypes.NOAUTH.value,
        IdentityManagerTypes.OAUTH2PROXY.value,
        "no_auth",  # backwards compatibility
        "single_tenant",  # backwards compatibility
    ]:
        # for oauth2proxy, we don't want to create the default user
        try_create_single_tenant(
            SINGLE_TENANT_UUID,
            create_default_user=(
                False if AUTH_TYPE == IdentityManagerTypes.OAUTH2PROXY.value else True
            ),
        )

    if os.environ.get("USE_NGROK", "false") == "true":
        from pyngrok import ngrok
        from pyngrok.conf import PyngrokConfig

        ngrok_config = PyngrokConfig(
            auth_token=os.environ.get("NGROK_AUTH_TOKEN", None)
        )
        # If you want to use a custom domain, set the NGROK_DOMAIN & NGROK_AUTH_TOKEN environment variables
        # read https://ngrok.com/blog-post/free-static-domains-ngrok-users -> https://dashboard.ngrok.com/cloud-edge/domains
        ngrok_connection = ngrok.connect(
            PORT,
            pyngrok_config=ngrok_config,
            domain=os.environ.get("NGROK_DOMAIN", None),
        )
        public_url = ngrok_connection.public_url
        logger.info(f"ngrok tunnel: {public_url}")
        os.environ["KEEP_API_URL"] = public_url

    if LIVE_DEMO_MODE:
        from keep.api.core.demo_mode_runner import launch_demo_mode
        launch_demo_mode()

    logger.info("Keep server started")
