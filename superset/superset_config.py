# Based on https://medium.com/@khushbu.adav/embedding-superset-dashboards-in-your-react-application-7f282e3dbd88
# Set logging level
import logging
from logging.config import dictConfig

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
KEEP_DATABASE_URI = "sqlite:////shared-db/dbtest.db?check_same_thread=false"
SECRET_KEY = "u/ZysbeXJxNuQQXLuBTyX2M6QKYMIkMqd9BvEm8XbEiw2NG1mibbMvLO"

CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],
    # Add this line
    "expose_headers": ["*"],
}

HTTP_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Origin,Content-Type,Accept,Authorization,X-GuestToken",
}

ALLOW_ORIGINS = [
    "http://localhost:8088",
    "http://localhost:8080",
    "http://localhost:3000",
]
# Talisman Config
TALISMAN_ENABLED = False
"""
TALISMAN_CONFIG = {
    "content_security_policy": {"frame-ancestors": ALLOW_ORIGINS},
    "force_https": False,
    "force_https_permanent": False,
    "frame_options": "ALLOWFROM",
    "frame_options_allow_from": "*",
}
"""

WEBDRIVER_BASEURL = "http://localhost:8088"

DEBUG = True
FLASK_DEBUG = True


class CustomLoggingConfigurator:
    def __init__(self, config):
        self.config = config

    def configure_logging(
        self, app, skip_if_exists=True
    ):  # Added skip_if_exists parameter
        dictConfig(self.config)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "/app/pythonpath/superset.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "superset": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        }
    },
}

# Create an instance of the configurator with our config
LOGGING_CONFIGURATOR = CustomLoggingConfigurator(LOGGING_CONFIG)

# Enable debug mode
DEBUG = True
FLASK_DEBUG = True


# Set basic logging level
def FLASK_APP_MUTATOR(app):
    app.logger.setLevel(logging.DEBUG)
