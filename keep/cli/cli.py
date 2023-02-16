import logging
import logging.config
import sys
from dataclasses import fields
from importlib import metadata

import click
import yaml
from dotenv import find_dotenv, load_dotenv

from keep.alertmanager.alertmanager import AlertManager
from keep.providers.providers_factory import ProvidersFactory

load_dotenv(find_dotenv())
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
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
        "": {  # root logger
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
logger = logging.getLogger(__name__)


class Info():
    """An information object to pass data between CLI functions."""

    def __init__(self):  # Note: This object must have an empty constructor.
        """Create a new instance."""
        self.verbose: int = 0
        self.config = {}
        self.logger = logging.getLogger(__name__)

    def set_config(self, keep_config: str):
        """Set the config file."""
        try:
            with open(file=keep_config, mode="r") as f:
                self.logger.debug("Loading configuration file.")
                self.config = yaml.safe_load(f)
                self.logger.debug("Configuration file loaded.")
        except FileNotFoundError:
            logger.debug(
                "Configuration file could not be found. Running without configuration.",
            )
            pass


# pass_info is a decorator for functions that pass 'Info' objects.
#: pylint: disable=invalid-name
pass_info = click.make_pass_decorator(Info, ensure=True)


# Change the options to below to suit the actual options for your task (or
# tasks).
@click.group()
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@click.option("--json", "-j", default=False, is_flag=True, help="Enable json output.")
@click.option(
    "--keep-config",
    "-c",
    help="The path to the keep config file",
    required=False,
    default="keep.yaml",
)
@pass_info
def cli(info: Info, verbose: int, json: bool, keep_config: str):
    """Run Keep CLI."""
    # Use the verbosity count to determine the logging level...
    if verbose > 0:
        # set the verbosity level to debug
        logging_config["loggers"][""]["level"] = "DEBUG"

    if json:
        logging_config["handlers"]["default"]["formatter"] = "json"
    logging.config.dictConfig(logging_config)
    info.verbose = verbose
    info.set_config(keep_config)


@cli.command()
def version():
    """Get the library version."""
    click.echo(click.style(f"{metadata.version('keep')}", bold=True))


@cli.command()
@click.option(
    "--alerts-file",
    "-f",
    type=click.Path(exists=True),
    help="The path to the alert yaml",
    required=True,
)
@click.option(
    "--providers-file",
    "-p",
    type=click.Path(exists=True),
    help="The path to the providers yaml",
    required=False,
    default="providers.yaml",
)
@click.option("--api-key", help="The API key for keep's API", required=False)
@click.option(
    "--api-url",
    help="The URL for keep's API",
    required=False,
    default="https://s.keephq.dev",
)
@pass_info
def run(info: Info, alerts_file, providers_file, api_key, api_url):
    """Run the alert."""
    logger.debug(f"Running alert {alerts_file}")
    alert_manager = AlertManager()
    try:
        alert_manager.run(alerts_file, providers_file)
    except Exception as e:
        logger.error(f"Error running alert {alerts_file}: {e}")
        if info.verbose:
            raise e
        sys.exit(1)
    logger.debug(f"Alert {alerts_file} ran successfully")


@cli.command()
@click.option(
    "--keep-config-file",
    type=click.Path(exists=False),
    help="The path to keeps config file [default: keep.yaml]",
    required=False,
    default="keep.yaml",
)
@pass_info
def init(info: Info, keep_config_file):
    """Set the config."""
    with open(keep_config_file, "w") as f:
        f.write("api_key: " + click.prompt("Enter your api key", hide_input=True))
    click.echo(click.style(f"Config file created at {keep_config_file}", bold=True))


@cli.group()
def config():
    """Set keep configuration."""
    pass


@config.command()
@click.option(
    "--provider-type",
    "-p",
    help="The provider to configure [e.g. elastic]",
    required=True,
)
@click.option(
    "--provider-id",
    "-i",
    help="The provider unique identifier [e.g. elastic-prod]",
    required=True,
)
@click.option(
    "--provider-config-file",
    "-c",
    help="The provider config",
    required=False,
    default="providers.yaml",
)
@pass_info
def provider(info: Info, provider_type, provider_id, provider_config_file):
    """Set the provider configuration."""
    click.echo(click.style(f"Config file: {provider_config_file}", bold=True))
    # create the file if it doesn't exist
    with open(provider_config_file, "a+") as f:
        pass
    # read the appropriate provider config
    config_class = ProvidersFactory.get_provider_required_config(provider_type)
    provider_config = {"authentication": {}}
    config = None
    while not config:
        # iterate necessary config and prompt for values
        for field in fields(config_class):
            optional = not field.metadata.get("required")
            if optional:
                default = field.default or ""
                config_value = click.prompt(
                    f"{field.metadata.get('description')}", default=default,
                )
            else:
                config_value = click.prompt(f"{field.metadata.get('description')}")
            provider_config["authentication"][field.name] = config_value

        try:
            config = config_class(**provider_config["authentication"])
        # If the validation failed, we need to reprompt the provider config
        except Exception as e:
            print(" -- Validation failed -- ")
            print(str(e))
            print(" -- Reconfiguring provider -- ")
    # Finally, let's keep the provider config
    with open(provider_config_file, "r") as f:
        providers = yaml.safe_load(f) or {}
    with open(provider_config_file, "w") as f:
        providers[provider_id] = provider_config
        yaml.dump(providers, f)
    click.echo(click.style(f"Config file created at {provider_config_file}", bold=True))


if __name__ == "__main__":
    cli(auto_envvar_prefix="KEEP")
