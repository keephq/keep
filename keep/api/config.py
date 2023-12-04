import logging
import os

import keep.api.logging
from keep.api.core.db import create_db_and_tables, try_create_single_tenant
from keep.api.core.dependencies import SINGLE_TENANT_UUID

PORT = int(os.environ.get("PORT", 8080))

keep.api.logging.setup()
logger = logging.getLogger(__name__)


def on_starting(server=None):
    """This function is called by the gunicorn server when it starts"""
    if not os.environ.get("SKIP_DB_CREATION", "false") == "true":
        create_db_and_tables()
    try_create_single_tenant(SINGLE_TENANT_UUID)

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
