import logging
import sys
from importlib import metadata

import click
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from keep.alertmanager.alertmanager import AlertManager

logger = logging.getLogger(__name__)


class Info(object):
    """An information object to pass data between CLI functions."""

    def __init__(self):  # Note: This object must have an empty constructor.
        """Create a new instance."""
        self.verbose: int = 0


# pass_info is a decorator for functions that pass 'Info' objects.
#: pylint: disable=invalid-name
pass_info = click.make_pass_decorator(Info, ensure=True)


# Change the options to below to suit the actual options for your task (or
# tasks).
@click.group()
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@pass_info
def cli(info: Info, verbose: int):
    """Run Keep CLI."""
    # Use the verbosity count to determine the logging level...
    if verbose > 0:
        logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    else:
        logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
    info.verbose = verbose


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
@pass_info
def run(info: Info, alerts_file, providers_dir):
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


if __name__ == "__main__":
    cli()
