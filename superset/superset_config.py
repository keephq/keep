# Based on https://medium.com/@khushbu.adav/embedding-superset-dashboards-in-your-react-application-7f282e3dbd88

SESSION_COOKIE_SAMESITE = None
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = False

# Dashboard embedding
# https://github.com/apache/superset/discussions/18814#discussioncomment-4056030
# https://github.com/apache/superset/issues/22258
# PUBLIC_ROLE_LIKE_GAMMA = True
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_SECRET = "CUSTOM_GUEST_TOKEN_JWT_SECRET"
GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes


# ENABLE_PROXY_FIX = True

FEATURE_FLAGS = {"EMBEDDED_SUPERSET": True}
# allow sqlite to be used for superset
PREVENT_UNSAFE_DB_CONNECTIONS = False
SQLALCHEMY_DATABASE_URI = "sqlite:////app/pythonpath/superset.db"
SECRET_KEY = "u/ZysbeXJxNuQQXLuBTyX2M6QKYMIkMqd9BvEm8XbEiw2NG1mibbMvLO"

CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],
}

ALLOW_ORIGINS = [
    "http://localhost:8088",
    "http://localhost:8080",
    "http://localhost:3000",
]
# Talisman Config
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    "content_security_policy": {"frame-ancestors": ALLOW_ORIGINS},
    "force_https": False,
    "force_https_permanent": False,
    "frame_options": "ALLOWFROM",
    "frame_options_allow_from": "*",
}

WEBDRIVER_BASEURL = "http://localhost:8088"
