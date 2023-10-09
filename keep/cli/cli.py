import json
import logging
import logging.config
import sys
import typing
from dataclasses import fields
from importlib import metadata

import click
import requests
import yaml
from dotenv import find_dotenv, load_dotenv
from prettytable import PrettyTable

from keep.api.core.db import get_api_key, try_create_single_tenant
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.cli.click_extensions import NotRequiredIf
from keep.posthog.posthog import get_posthog_client, get_random_user_id
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.workflowmanager.workflowstore import WorkflowStore

load_dotenv(find_dotenv())
posthog_client = get_posthog_client()

RANDOM_USER_ID = get_random_user_id()


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
        }
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        }
    },
}
logger = logging.getLogger(__name__)


class Info:
    """An information object to pass data between CLI functions."""

    def __init__(self):  # Note: This object must have an empty constructor.
        """Create a new instance."""
        self.verbose: int = 0
        self.config = {}
        self.json = False
        self.logger = logging.getLogger(__name__)

    def set_config(self, keep_config: str):
        """Set the config file."""
        try:
            with open(file=keep_config, mode="r") as f:
                self.logger.debug("Loading configuration file.")
                self.config = yaml.safe_load(f)
                self.api_key = (
                    self.config.get("api_key") or os.getenv("KEEP_API_KEY") or ""
                )
                self.keep_api_url = self.config.get("keep_api_url") or os.getenv(
                    "KEEP_API_URL"
                )
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
@click.option("--json", "-j", default=False, is_flag=True, help="Enable json output.")
@click.option(
    "--keep-config",
    "-c",
    help="The path to the keep config file",
    required=False,
    default="keep.yaml",
)
@pass_info
@click.pass_context
def cli(ctx, info: Info, verbose: int, json: bool, keep_config: str):
    """Run Keep CLI."""
    # https://posthog.com/tutorials/identifying-users-guide#identifying-and-setting-user-ids-for-every-other-library
    # random user id
    posthog_client.capture(
        RANDOM_USER_ID,
        "keep-cli-started",
        properties={
            "args": sys.argv,
        },
    )
    # Use the verbosity count to determine the logging level...
    if verbose > 0:
        # set the verbosity level to debug
        logging_config["loggers"][""]["level"] = "DEBUG"

    if json:
        logging_config["handlers"]["default"]["formatter"] = "json"
    logging.config.dictConfig(logging_config)
    info.verbose = verbose
    info.set_config(keep_config)
    info.json = json

    @ctx.call_on_close
    def cleanup():
        if posthog_client:
            posthog_client.flush()


@cli.command()
def version():
    """Get the library version."""
    click.echo(click.style(f"{metadata.version('keep')}", bold=True))


@cli.command()
@pass_info
def whoami(info: Info):
    """Verify the api key auth."""
    resp = requests.get(
        info.keep_api_url + "/whoami",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )

    if resp.status_code == 401:
        click.echo(click.style("Api key invalid"))

    elif resp.ok:
        click.echo(click.style("Api key valid"))
        click.echo(resp.json())
    else:
        click.echo(click.style("Api key invalid [unknown error]"))


@cli.command()
@click.option("--multi-tenant", is_flag=True, help="Enable multi-tenant mode")
def api(multi_tenant: bool):
    """Start the API."""
    from keep.api import api

    ctx = click.get_current_context()
    app = api.get_app(multi_tenant=multi_tenant)
    logger.info(f"App initialized, multi tenancy: {multi_tenant}")
    app.dependency_overrides[click.get_current_context] = lambda: ctx
    api.run(app)


@cli.command()
@click.option(
    "--alerts-directory",
    "--alerts-file",
    "-af",
    type=click.Path(exists=True, dir_okay=True, file_okay=True),
    help="The path to the alert yaml/alerts directory",
)
@click.option(
    "--alert-url",
    "-au",
    help="A url that can be used to download an alert yaml",
    cls=NotRequiredIf,
    multiple=True,
    not_required_if="alerts_directory",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    help="When interval is set, Keep will run the alert every INTERVAL seconds",
    required=False,
    default=0,
)
@click.option(
    "--providers-file",
    "-p",
    type=click.Path(exists=False),
    help="The path to the providers yaml",
    required=False,
    default="providers.yaml",
)
@click.option(
    "--tenant-id",
    "-t",
    help="The tenant id",
    required=False,
    default=SINGLE_TENANT_UUID,
)
@click.option("--api-key", help="The API key for keep's API", required=False)
@click.option(
    "--api-url",
    help="The URL for keep's API",
    required=False,
    default="https://s.keephq.dev",
)
@pass_info
def run(
    info: Info,
    alerts_directory: str,
    alert_url: list[str],
    interval: int,
    providers_file,
    tenant_id,
    api_key,
    api_url,
):
    """Run the alert."""
    logger.debug(f"Running alert in {alerts_directory or alert_url}")
    posthog_client.capture(
        RANDOM_USER_ID,
        "keep-run-alert-started",
        properties={
            "args": sys.argv,
        },
    )
    # this should be fixed
    workflow_manager = WorkflowManager.get_instance()
    workflow_store = WorkflowStore()
    if tenant_id == SINGLE_TENANT_UUID:
        try_create_single_tenant(SINGLE_TENANT_UUID)
    workflows = workflow_store.get_workflows_from_path(
        tenant_id, alerts_directory or alert_url, providers_file
    )
    try:
        workflow_manager.run(workflows)
    except KeyboardInterrupt:
        logger.info("Keep stopped by user, stopping the scheduler")
        posthog_client.capture(
            RANDOM_USER_ID,
            "keep-run-stopped-by-user",
            properties={
                "args": sys.argv,
            },
        )
        workflow_manager.stop()
        logger.info("Scheduler stopped")
    except Exception as e:
        posthog_client.capture(
            RANDOM_USER_ID,
            "keep-run-unexpected-error",
            properties={
                "args": sys.argv,
                "error": str(e),
            },
        )
        logger.error(f"Error running alert {alerts_directory or alert_url}: {e}")
        if info.verbose:
            raise e
        sys.exit(1)
    posthog_client.capture(
        RANDOM_USER_ID,
        "keep-run-alert-finished",
        properties={
            "args": sys.argv,
        },
    )
    logger.debug(f"Alert in {alerts_directory or alert_url} ran successfully")


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
@pass_info
def workflow(info: Info):
    """Manage workflows."""
    pass


@workflow.command()
@pass_info
def list(info: Info):
    """List workflows."""
    resp = requests.get(
        info.keep_api_url + "/workflows",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting workflows: {resp.text}")

    workflows = resp.json()
    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Name",
        "Description",
        "Created By",
        "Creation Time",
        "Last Execution Time",
        "Last Execution Status",
    ]
    # TODO - add triggers, steps, actions -> the table format should be better
    # Add rows for each workflow
    for workflow in workflows:
        table.add_row(
            [
                workflow["id"],
                workflow["description"],
                workflow["workflow_raw_id"],
                workflow["created_by"],
                workflow["creation_time"],
                workflow["last_execution_time"],
                workflow["last_execution_status"],
            ]
        )
    print(table)


@workflow.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="The workflow file",
    required=True,
)
def apply(file_path: str):
    """Apply a workflow."""
    with open(file_path, "rb") as file:
        files = {
            "file": (file_path.split("/")[-1], file)
        }  # The field 'file' should match the name in the API endpoint
        response = requests.post(url, headers=headers, files=files)


@cli.group()
@pass_info
def provider(info: Info):
    """Manage providers."""
    pass


@provider.command()
@click.option(
    "--available",
    "-a",
    default=False,
    is_flag=True,
    help="List provider that you can install.",
)
@pass_info
def list(info: Info, available: bool):
    """List providers."""
    resp = requests.get(
        info.keep_api_url + "/providers",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting providers: {resp.text}")

    providers = resp.json()
    # Create a new table
    table = PrettyTable()
    # Add column headers
    if available:
        available_providers = providers.get("providers", [])
        # sort alphabetically by type
        available_providers.sort(key=lambda x: x.get("type"))
        table.field_names = ["Provider", "Description"]
        for provider in available_providers:
            provider_type = provider.get("type")
            provider_docs = provider.get("docs", "")
            if provider_docs:
                provider_docs = provider_docs.replace("\n", " ").strip()
            else:
                provider_docs = ""
            table.add_row(
                [
                    provider_type,
                    provider_docs,
                ]
            )
    else:
        table.field_names = ["ID", "Type", "Name", "Installed by", "Installation time"]
        installed_providers = providers.get("installed_providers", [])
        installed_providers.sort(key=lambda x: x.get("type"))
        for provider in installed_providers:
            table.add_row(
                [
                    provider["id"],
                    provider["type"],
                    provider["details"]["name"],
                    provider["installed_by"],
                    provider["installation_time"],
                ]
            )
    print(table)


@provider.command(context_settings=dict(ignore_unknown_options=True))
@click.option(
    "--help",
    "-h",
    default=False,
    is_flag=True,
    help="Help on how to install this provider.",
)
@click.option(
    "--provider-name",
    "-n",
    required=False,
    help="Every provider shuold have a name.",
)
@click.argument("provider_type")
@click.argument("params", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def connect(ctx, help: bool, provider_name, provider_type, params):
    info = ctx.ensure_object(Info)
    resp = requests.get(
        info.keep_api_url + "/providers",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting providers: {resp.text}")

    available_providers = providers = resp.json().get("providers")

    provider = [p for p in available_providers if p.get("type") == provider_type]
    if not provider:
        click.echo(
            click.style(
                f"Provider {provider_type} not found, you can open an issue and we will create it within a blink of an eye https://github.com/keephq/keep",
                bold=True,
            )
        )
    provider = provider[0]
    if help:
        table = PrettyTable()
        table.field_names = [
            "Provider",
            "Config Param",
            "Required",
            "Description",
        ]
        provider_type = provider.get("type")
        for param, details in provider["config"].items():
            table.add_row(
                [
                    provider_type,
                    param,
                    details.get("required", False),
                    details.get("description", "no description"),
                ]
            )
            # Reset the provider_type for subsequent rows of the same provider to avoid repetition
            provider_type = ""
        print(table)
        return

    if not provider_name:
        # exit with error
        raise click.BadOptionUsage(
            "--provider-name",
            f"Required option --provider-name not provided for provider {provider_type}",
        )

    # Connect the provider
    raw_opts = ctx.args
    options_dict = {params[i]: params[i + 1] for i in range(0, len(params), 2)}
    # Verify the provided options against the expected ones for the provider

    provider_install_payload = {
        "provider_id": provider["type"],
        "provider_name": provider_name,
    }
    for config in provider["config"]:
        config_as_flag = f"--{config.replace('_', '-')}"
        if config_as_flag not in options_dict and provider["config"][config].get(
            "required", True
        ):
            raise click.BadOptionUsage(
                config_as_flag,
                f"Required option --{config} not provided for provider {provider_name}",
            )
        if config_as_flag in options_dict:
            provider_install_payload[config] = options_dict[config_as_flag]
    # Install the provider
    resp = requests.post(
        info.keep_api_url + "/providers/install",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=provider_install_payload,
    )
    if not resp.ok:
        click.echo(
            click.style(
                f"Error installing provider {provider_name}: {resp.text}", bold=True
            )
        )
    else:
        resp = resp.json()
        click.echo(
            click.style(f"Provider {provider_name} installed successfully", bold=True)
        )
        click.echo(click.style(f"Provider id: {resp.get('id')}", bold=True))


@cli.group()
@pass_info
def alert(info: Info):
    """Manage alerts."""
    pass


@cli.group()
def config():
    """Set keep configuration."""
    pass


@alert.command()
@click.option(
    "--filter",
    "-f",
    type=str,
    multiple=True,
    help="Filter alerts based on specific attributes. E.g., --filter source=datadog",
)
@click.option(
    "--export", type=click.Path(), help="Export alerts to a specified JSON file."
)
@pass_info
def list(info: Info, filter: typing.List[str], export: bool):
    """List alerts."""
    resp = requests.get(
        info.keep_api_url + "/alerts",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting providers: {resp.text}")

    alerts = resp.json()

    # Apply all provided filters
    for filt in filter:
        key, value = filt.split("=")
        alerts = [alert for alert in alerts if alert.get(key) == value]

    # If --export option is provided
    if export:
        with open(export, "w") as outfile:
            json.dump(alerts, outfile, indent=4)
        click.echo(f"Alerts exported to {export}")
        return

    # Create a new table
    table = PrettyTable()
    table.field_names = [
        "ID",
        "Fingerprint",
        "Name",
        "Status",
        "Environment",
        "Service",
        "Source",
        "Last Received",
    ]
    table.max_width["ID"] = 20
    table.max_width["Name"] = 30
    table.max_width["Status"] = 10
    table.max_width["Environment"] = 15
    table.max_width["Service"] = 15
    table.max_width["Source"] = 15
    table.max_width["Last Received"] = 30
    for alert in alerts:
        table.add_row(
            [
                alert["id"],
                alert["fingerprint"],
                alert["name"],
                alert["status"],
                alert["environment"],
                alert["service"],
                alert["source"],
                alert["lastReceived"],
            ]
        )
    print(table)


@alert.command()
@click.option("--alert-id", required=True, help="ID of the alert to enrich.")
@click.argument("params", nargs=-1, type=click.UNPROCESSED)
@pass_info
def enrich(info: Info, alert_id, params):
    """Enrich an alert."""

    # Convert arguments to dictionary
    if len(params) % 2 != 0:
        raise click.BadArgumentUsage("Parameters must be given in key=value pairs")

    params_dict = {params[i]: params[i + 1] for i in range(0, len(params), 2)}

    # Make the API request
    resp = requests.post(
        f"{info.keep_api_url}/alerts/{alert_id}/enrich",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=params_dict,
    )

    # Check the response
    if not resp.ok:
        click.echo(
            click.style(f"Error enriching alert {alert_id}: {resp.text}", bold=True)
        )
    else:
        click.echo(click.style(f"Alert {alert_id} enriched successfully", bold=True))


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
            is_sensitive = field.metadata.get("sensitive", False)
            optional = not field.metadata.get("required")
            if optional:
                default = field.default or ""
                config_value = click.prompt(
                    f"{field.metadata.get('description')}",
                    default=default,
                    hide_input=is_sensitive,
                )
            else:
                config_value = click.prompt(
                    f"{field.metadata.get('description')}", hide_input=is_sensitive
                )
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
