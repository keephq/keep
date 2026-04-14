import logging
import logging.config
import os
from dotenv import load_dotenv


# Load env variables
load_dotenv()


class MezmoProvider:
    """
    Mezmo (formerly LogDNA) logging provider.
    
    Provides structured logging with optional Mezmo cloud integration.
    Falls back to console logging if Mezmo key is not configured.
    
    Example:
        provider = MezmoProvider()
        logger = provider.get_logger()
        logger.info("Hello from Keep!")
    """

    def __init__(self, mezmo_key: str | None = None, app: str = "Keep", env: str = "production", hostname: str = "keep-server"):
        self.mezmo_key = MEZMO_INGESTION_KEY or os.environ.get("MEZMO_INGESTION_KEY")
        self.app = app
        self.env = env
        self.hostname = hostname
        self.logger = self._setup_logger()

    def _build_config(self) -> dict:
        logging_config = {
            "version" : 1,
            "disable_existing_loggers" : False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
            "json": {
                "format": "%(asctime)s %(message)s %(levelname)s %(name)s %(filename)s %(lineno)d",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "keep": {  # root logger
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            }
        },
    }

        # Only add Mezmo handler if the key is present
        if self.mezmo_key:
            logging_config["handlers"]["mezmo"] = {
                "class": "logdna.LogDNAHandler",
                "key": self.mezmo_key,
                "options": {
                    "app": self.app,
                    "env": self.env,
                    "hostname": self.hostname,
                },
                "level": "INFO",
            }
            logging_config["loggers"]["keep"]["handlers"].append("mezmo")
    
        return logging_config

    def _setup_logger(self) -> logging.Logger:
        config = self._build_config()
        logging.config.dictConfig(config)
        return logging.getLogger("keep")

    def get_logger(self) -> logging.Logger:
        return self.logger

if __name__ == "__main__":

    MEZMO_INGESTION_KEY = os.environ.get("MEZMO_INGESTION_KEY")

    # Check Investigation key is correct or not
    if not MEZMO_INGESTION_KEY:
        raise ValueError("MEZMO_INGESTION_KEY is missing or empty")
    
    provider = MezmoProvider()
    logger = provider.get_logger()
