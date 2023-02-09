import logging
import sys
from importlib import metadata

import click
import yaml
from dotenv import find_dotenv, load_dotenv

from keep.alertmanager.alertmanager import AlertManager

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)


class Info(object):
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
                "Configuration file could not be found. Running without configuration."
            )
            pass


# pass_info is a decorator for functions that pass 'Info' objects.
#: pylint: disable=invalid-name
pass_info = click.make_pass_decorator(Info, ensure=True)


# Change the options to below to suit the actual options for your task (or
# tasks).
@click.group()
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@click.option(
    "--keep-config",
    "-c",
    help="The path to the keep config file",
    required=False,
    default="keep.yaml",
)
@pass_info
def cli(info: Info, verbose: int, keep_config: str):
    """Run Keep CLI."""
    # Use the verbosity count to determine the logging level...
    if verbose > 0:
        logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    else:
        logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
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
    "--providers-dir",
    type=click.Path(exists=True),
    help="The path to the providers directory",
    required=False,
)
@click.option("--api-key", help="The API key for keep's API", required=False)
@click.option(
    "--api-url",
    help="The URL for keep's API",
    required=False,
    default="https://s.keephq.dev",
)
@pass_info
def run(info: Info, alerts_file, providers_dir, api_key, api_url):
    """Run the alert."""
    logger.debug(f"Running alert {alerts_file}")
    alert_manager = AlertManager()
    try:
        alert_manager.run(alerts_file)
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
    help="The path to keeps config file [default: keep.yaml]]",
    required=False,
    default="keep.yaml",
)
@pass_info
def init(info: Info, keep_config_file):
    """Set the config."""
    with open(keep_config_file, "w") as f:
        f.write("api_key: " + click.prompt("Enter your api key", hide_input=True))
    click.echo(click.style(f"Config file created at {keep_config_file}", bold=True))


if __name__ == "__main__":
    cli(auto_envvar_prefix="KEEP")
