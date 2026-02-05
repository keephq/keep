from auth0.authentication import GetToken
from auth0.management import Auth0

from keep.api.core.config import config


def getAuth0Client() -> Auth0:
    AUTH0_DOMAIN = config("AUTH0_MANAGEMENT_DOMAIN")
    AUTH0_CLIENT_ID = config("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = config("AUTH0_CLIENT_SECRET")
    get_token = GetToken(AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET)
    token = get_token.client_credentials("https://{}/api/v2/".format(AUTH0_DOMAIN))
    mgmt_api_token = token["access_token"]
    auth0 = Auth0(AUTH0_DOMAIN, mgmt_api_token)
    return auth0
