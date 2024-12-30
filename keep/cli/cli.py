import json
import logging
import logging.config
import os
import sys
import typing
import uuid
from collections import OrderedDict
from dataclasses import _MISSING_TYPE
from importlib import metadata

import click
import requests
import yaml
from dotenv import find_dotenv, load_dotenv
from prettytable import PrettyTable

from keep.api.core.posthog import posthog_client
from keep.providers.models.provider_config import ProviderScope
from keep.providers.providers_factory import ProvidersFactory

load_dotenv(find_dotenv())

try:
    KEEP_VERSION = metadata.version("keep")
except metadata.PackageNotFoundError:
    try:
        KEEP_VERSION = metadata.version("keephq")
    except metadata.PackageNotFoundError:
        KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")

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


def get_default_conf_file_path():
    DEFAULT_CONF_FILE = ".keep.yaml"
    from pathlib import Path

    home = str(Path.home())
    return os.path.join(home, DEFAULT_CONF_FILE)


def make_keep_request(method, url, **kwargs):
    if os.environ.get("KEEP_CLI_IGNORE_SSL", "false").lower() == "true":
        kwargs['verify'] = False
    try:
        response = requests.request(method, url, **kwargs)
        if response.status_code == 401:
            click.echo(
                click.style(
                    "Authentication failed. Please check your API key.",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit(401)
        return response
    except requests.exceptions.RequestException as e:
        click.echo(click.style(f"Request failed: {e}", fg="red", bold=True))
        sys.exit(1)


class Info:
    """An information object to pass data between CLI functions."""

    KEEP_MANAGED_API_URL = "https://api.keephq.dev"

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
                self.config = yaml.safe_load(f) or {}
                self.logger.debug("Configuration file loaded.")

        except FileNotFoundError:
            logger.debug(
                "Configuration file could not be found. Running without configuration."
            )
            pass
        self.api_key = self.config.get("api_key") or os.getenv("KEEP_API_KEY") or ""
        self.keep_api_url = (
            self.config.get("keep_api_url")
            or os.getenv("KEEP_API_URL")
            or Info.KEEP_MANAGED_API_URL
        )
        self.random_user_id = self.config.get("random_user_id")
        # if we don't have a random user id, we create one and keep it on the config file
        if not self.random_user_id:
            self.random_user_id = str(uuid.uuid4())
            self.config["random_user_id"] = self.random_user_id
            with open(file=keep_config, mode="w") as f:
                yaml.dump(self.config, f)

        arguments = sys.argv

        # if we auth, we don't need to check for api key
        if (
            "auth" in arguments
            or "api" in arguments
            or "config" in arguments
            or "version" in arguments
            or "build_cache" in arguments
        ):
            return

        if not self.api_key:
            click.echo(
                click.style(
                    "No api key found. Please run `keep config` to set the api key or set KEEP_API_KEY env variable.",
                    bold=True,
                )
            )
            sys.exit(2)

        if not self.keep_api_url:
            click.echo(
                click.style(
                    "No keep api url found. Please run `keep config` to set the keep api url or set KEEP_API_URL env variable.",
                    bold=True,
                )
            )
            sys.exit(2)

        click.echo(
            click.style(
                f"Using keep api url: {self.keep_api_url}",
                bold=True,
            )
        )


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
    help=f"The path to the keep config file (default {get_default_conf_file_path()}",
    required=False,
    default=f"{get_default_conf_file_path()}",
)
@pass_info
@click.pass_context
def cli(ctx, info: Info, verbose: int, json: bool, keep_config: str):
    """Run Keep CLI."""
    # https://posthog.com/tutorials/identifying-users-guide#identifying-and-setting-user-ids-for-every-other-library
    # random user id
    info.set_config(keep_config)
    posthog_client.capture(
        info.random_user_id,
        "keep-cli-started",
        properties={
            "args": sys.argv,
            "keep_version": KEEP_VERSION,
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
    info.json = json

    @ctx.call_on_close
    def cleanup():
        if posthog_client:
            posthog_client.flush()


@cli.command()
def version():
    """Get the library version."""
    click.echo(click.style(KEEP_VERSION, bold=True))


@cli.group()
@pass_info
def config(info: Info):
    """Manage the config."""
    pass


@config.command(name="show")
@pass_info
def show(info: Info):
    """show the current config."""
    click.echo(click.style("Current config", bold=True))
    for key, value in info.config.items():
        click.echo(f"{key}: {value}")


@config.command(name="new")
@click.option(
    "--url",
    "-u",
    type=str,
    required=False,
    is_flag=False,
    flag_value="http://localhost:8080",
    help="The url of the keep api",
)
@click.option(
    "--api-key",
    "-a",
    type=str,
    required=False,
    is_flag=False,
    flag_value="",
    help="The api key for keep",
)
@click.option(
    "--interactive",
    "-i",
    help="Interactive mode creating keep config (default True)",
    is_flag=True,
)
@pass_info
def new_config(info: Info, url: str, api_key: str, interactive: bool):
    """create new config."""
    ctx = click.get_current_context()

    if not interactive:
        keep_url = ctx.params.get("url")
        api_key = ctx.params.get("api_key")
    else:
        keep_url = click.prompt("Enter your keep url", default="http://localhost:8080")
        api_key = click.prompt(
            "Enter your api key (leave blank for localhost)",
            hide_input=True,
            default="",
        )
    if not api_key:
        api_key = "localhost"
    with open(f"{get_default_conf_file_path()}", "w") as f:
        f.write(f"api_key: {api_key}\n")
        f.write(f"keep_api_url: {keep_url}\n")
        f.write(f"random_user_id: {info.random_user_id}\n")
    click.echo(
        click.style(f"Config file created at {get_default_conf_file_path()}", bold=True)
    )


@cli.command()
@pass_info
def whoami(info: Info):
    """Verify the api key auth."""
    try:
        resp = make_keep_request(
            "GET",
            info.keep_api_url + "/whoami",
            headers={"x-api-key": info.api_key, "accept": "application/json"},
        )
    except requests.exceptions.ConnectionError:
        click.echo(click.style(f"Timeout connecting to {info.keep_api_url}"))
        sys.exit(1)

    if resp.status_code == 401:
        click.echo(click.style("Api key invalid"))

    elif resp.ok:
        click.echo(click.style("Api key valid"))
        click.echo(resp.json())
    else:
        click.echo(click.style("Api key invalid [unknown error]"))


@cli.command()
@click.option("--multi-tenant", is_flag=True, help="Enable multi-tenant mode")
@click.option(
    "--port",
    "-p",
    type=int,
    default=int(os.environ.get("PORT", 8080)),
    help="The port to run the API on",
)
@click.option(
    "--host",
    "-h",
    type=str,
    default=os.environ.get("HOST", "0.0.0.0"),
    help="The host to run the API on",
)
def api(multi_tenant: bool, port: int, host: str):
    """Start the API."""
    from keep.api import api

    ctx = click.get_current_context()

    api.PORT = ctx.params.get("port")
    api.HOST = ctx.params.get("host")

    if multi_tenant:
        auth_type = "MULTI_TENANT"
    else:
        auth_type = "NO_AUTH"
    app = api.get_app(auth_type=auth_type)
    logger.info(
        f"App initialized, multi tenancy flag from user [overriden by AUTH_TYPE env var]: {multi_tenant}"
    )
    app.dependency_overrides[click.get_current_context] = lambda: ctx
    api.run(app)


@cli.group()
@pass_info
def workflow(info: Info):
    """Manage workflows."""
    pass


@workflow.command(name="list")
@pass_info
def list_workflows(info: Info):
    """List workflows."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/workflows",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting workflows: {resp.text}")

    workflows = resp.json()
    if len(workflows) == 0:
        click.echo(click.style("No workflows found.", bold=True))
        return

    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Name",
        "Description",
        "Revision",
        "Created By",
        "Creation Time",
        "Update Time",
        "Last Execution Time",
        "Last Execution Status",
    ]
    # TODO - add triggers, steps, actions -> the table format should be better
    # Add rows for each workflow
    for workflow in workflows:
        table.add_row(
            [
                workflow["id"],
                workflow["name"],
                workflow["description"],
                workflow["revision"],
                workflow["created_by"],
                workflow["creation_time"],
                workflow["last_updated"],
                workflow["last_execution_time"],
                workflow["last_execution_status"],
            ]
        )
    print(table)


def apply_workflow(file: str, info: Info):
    """Helper function to apply a single workflow."""
    with open(file, "rb") as f:
        files = {"file": (os.path.basename(file), f)}
        workflow_endpoint = info.keep_api_url + "/workflows"
        response = make_keep_request(
            "POST",
            workflow_endpoint,
            headers={"x-api-key": info.api_key, "accept": "application/json"},
            files=files,
        )
        return response


@workflow.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="The workflow file or directory containing workflow files",
    required=True,
)
@pass_info
def apply(info: Info, file: str):
    """Apply a workflow or multiple workflows from a directory."""
    if os.path.isdir(file):
        for filename in os.listdir(file):
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                click.echo(click.style(f"Applying workflow {filename}", bold=True))
                full_path = os.path.join(file, filename)
                response = apply_workflow(full_path, info)
                # Handle response for each file
                if response.ok:
                    click.echo(
                        click.style(
                            f"Workflow {filename} applied successfully", bold=True
                        )
                    )
                else:
                    click.echo(
                        click.style(
                            f"Error applying workflow {filename}: {response.text}",
                            bold=True,
                        )
                    )
    else:
        response = apply_workflow(file, info)
        if response.ok:
            click.echo(click.style(f"Workflow {file} applied successfully", bold=True))
        else:
            click.echo(
                click.style(
                    f"Error applying workflow {file}: {response.text}", bold=True
                )
            )


@workflow.command(name="run")
@click.option(
    "--workflow-id",
    type=str,
    help="The ID (UUID or name) of the workflow to run",
    required=True,
)
@click.option(
    "--fingerprint",
    type=str,
    help="The fingerprint to query the payload",
    required=True,
)
@pass_info
def run_workflow(info: Info, workflow_id: str, fingerprint: str):
    """Run a workflow with a specified ID and fingerprint."""
    # Query the server for payload based on the fingerprint
    # Replace the following line with your actual logic to fetch the payload
    payload = _get_alert_by_fingerprint(info.keep_api_url, info.api_key, fingerprint)

    if not payload.ok:
        click.echo(click.style("Error: Failed to fetch alert payload", bold=True))
        return

    payload = payload.json()

    # Run the workflow with the fetched payload as the request body
    workflow_endpoint = info.keep_api_url + f"/workflows/{workflow_id}/run"
    response = make_keep_request(
        "POST",
        workflow_endpoint,
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=payload,
    )
    # Check the response
    if response.ok:
        response = response.json()
        click.echo(click.style(f"Workflow {workflow_id} run successfully", bold=True))
        click.echo(
            click.style(
                f"Workflow Run ID {response.get('workflow_execution_id')}", bold=True
            )
        )
    else:
        click.echo(
            click.style(
                f"Error running workflow {workflow_id}: {response.text}", bold=True
            )
        )


@workflow.group(name="runs")
@pass_info
def workflow_executions(info: Info):
    """Manage workflows executions."""
    pass


@workflow_executions.command(name="list")
@pass_info
def list_workflow_executions(info: Info):
    """List workflow executions."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/workflows/executions/list",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting workflow executions: {resp.text}")

    workflow_executions = resp.json()
    if len(workflow_executions) == 0:
        click.echo(click.style("No workflow executions found.", bold=True))
        return

    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Workflow ID",
        "Start Time",
        "Triggered By",
        "Status",
        "Error",
        "Execution Time",
    ]
    table.max_width["Error"] = 50
    table.align["Error"] = "l"
    # Add rows for each workflow execution
    for workflow_execution in workflow_executions:
        table.add_row(
            [
                workflow_execution["id"],
                workflow_execution["workflow_id"],
                workflow_execution["started"],
                workflow_execution["triggered_by"],
                workflow_execution["status"],
                workflow_execution.get("error", "N/A"),
                workflow_execution["execution_time"],
            ]
        )
    print(table)


@workflow_executions.command(name="logs")
@click.argument(
    "workflow_execution_id",
    required=True,
    type=str,
)
@pass_info
def get_workflow_execution_logs(info: Info, workflow_execution_id: str):
    """Get workflow execution logs."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url
        + "/workflows/executions/list?workflow_execution_id="
        + workflow_execution_id,
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting workflow executions: {resp.text}")

    workflow_executions = resp.json()

    workflow_execution_logs = workflow_executions[0].get("logs", [])
    if len(workflow_execution_logs) == 0:
        click.echo(click.style("No logs found for this workflow execution.", bold=True))
        return

    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Timestamp",
        "Message",
    ]
    table.align["Message"] = "l"
    # Add rows for each workflow execution
    for log in workflow_execution_logs:
        table.add_row([log["id"], log["timestamp"], log["message"]])
    print(table)


@cli.group()
@pass_info
def mappings(info: Info):
    """Manage mappings."""
    pass


@mappings.command(name="list")
@pass_info
def list_mappings(info: Info):
    """List mappings."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/mapping",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting mappings: {resp.text}")

    mappings = resp.json()
    if len(mappings) == 0:
        click.echo(click.style("No mappings found.", bold=True))
        return

    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Name",
        "Description",
        "Priority",
        "Matchers",
        "Attributes",
        "File Name",
        "Created By",
        "Creation Time",
    ]

    # Add rows for each mapping
    for mapping in mappings:
        table.add_row(
            [
                mapping["id"],
                mapping["name"],
                mapping["description"],
                mapping["priority"],
                ", ".join(mapping["matchers"]),
                ", ".join(mapping["attributes"]),
                mapping["file_name"],
                mapping["created_by"],
                mapping["created_at"],
            ]
        )
    print(table)


@mappings.command(name="create")
@click.option(
    "--name",
    "-n",
    type=str,
    help="The name of the mapping.",
    required=True,
)
@click.option(
    "--description",
    "-d",
    type=str,
    help="The description of the mapping.",
    required=False,
    default="",
)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="The mapping file. Must be a CSV file.",
    required=True,
)
@click.option(
    "--matchers",
    "-m",
    type=str,
    help="The matchers of the mapping, as a comma-separated list of strings.",
    required=True,
)
@click.option(
    "--priority",
    "-p",
    type=click.IntRange(0, 100),
    help="The priority of the mapping, higher priority means this rule will execute first.",
    required=False,
    default=0,
)
@pass_info
def create(
    info: Info, name: str, description: str, file: str, matchers: str, priority: int
):
    """Create a mapping rule."""
    if os.path.isfile(file) and file.endswith(".csv"):
        with open(file, "rb") as f:
            file_name = os.path.basename(file)
            try:
                csv_data = f.read().decode("utf-8")
                csv_rows = csv_data.split("\n")
                csv_headers = csv_rows[0].split(",")
                csv_rows = csv_rows[1:]
                rows = []
                for row in csv_rows:
                    if row:
                        row = row.split(",")
                        rows.append(OrderedDict(zip(csv_headers, row)))
            except Exception as e:
                click.echo(click.style(f"Error reading or processing CSV file: {e}"))
                return
            mappings_endpoint = info.keep_api_url + "/mapping"
            response = make_keep_request(
                "POST",
                mappings_endpoint,
                headers={"x-api-key": info.api_key, "accept": "application/json"},
                json={
                    "name": name,
                    "description": description,
                    "file_name": file_name,
                    "matchers": matchers.split(","),
                    "rows": rows,
                    "priority": priority,
                },
            )

        # Check the response
        if response.ok:
            click.echo(
                click.style(f"Mapping rule {file_name} created successfully", bold=True)
            )
        else:
            click.echo(
                click.style(
                    f"Error creating mapping rule {file_name}: {response.text}",
                    bold=True,
                )
            )


@mappings.command(name="delete")
@click.option(
    "--mapping-id",
    type=int,
    help="The ID of the mapping to delete.",
    required=True,
)
@pass_info
def delete_mapping(info: Info, mapping_id: int):
    """Delete a mapping with a specified ID."""

    # Delete the mapping with the specified ID
    mappings_endpoint = info.keep_api_url + f"/mapping/{mapping_id}"
    response = make_keep_request(
        "DELETE",
        mappings_endpoint,
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    # Check the response
    if response.ok:
        click.echo(
            click.style(f"Mapping rule {mapping_id} deleted successfully", bold=True)
        )
    else:
        click.echo(
            click.style(
                f"Error deleting mapping rule {mapping_id}: {response.text}", bold=True
            )
        )


@cli.group()
@pass_info
def extraction(info: Info):
    """Manage extractions."""
    pass


@extraction.command(name="list")
@pass_info
def list_extraction(info: Info):
    """List extractions."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/extraction",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting extractions: {resp.text}")

    extractions = resp.json()
    if len(extractions) == 0:
        click.echo(click.style("No extractions found.", bold=True))
        return

    # Create a new table
    table = PrettyTable()
    # Add column headers
    table.field_names = [
        "ID",
        "Name",
        "Description",
        "Priority",
        "Attribute",
        "Condition",
        "Disabled",
        "Regex",
        "Pre",
        "Created By",
        "Creation Time",
        "Updated By",
        "Update Time",
    ]

    # Add rows for each extraction
    for e in extractions:
        table.add_row(
            [
                e["id"],
                e["name"],
                e["description"],
                e["priority"],
                e["attribute"],
                e["condition"],
                e["disabled"],
                e["regex"],
                e["pre"],
                e["created_by"],
                e["created_at"],
                e["updated_by"],
                e["updated_at"],
            ]
        )
    print(table)


@extraction.command(name="create")
@click.option(
    "--name",
    "-n",
    type=str,
    help="The name of the extraction.",
    required=True,
)
@click.option(
    "--description",
    "-d",
    type=str,
    help="The description of the extraction.",
    required=False,
    default="",
)
@click.option(
    "--priority",
    "-p",
    type=click.IntRange(0, 100),
    help="The priority of the extraction, higher priority means this rule will execute first.",
    required=False,
    default=0,
)
@click.option(
    "--pre",
    type=bool,
    help="Whether this rule should be applied before or after the alert is standardized.",
    required=False,
    default=False,
)
@click.option(
    "--attribute",
    "-a",
    type=str,
    help="Event attribute name to extract from.",
    required=True,
    default="",
)
@click.option(
    "--regex",
    "-r",
    type=str,
    help="The regex rule to extract by. Regex format should be like python regex pattern for group matching.",
    required=True,
    default="",
)
@click.option(
    "--condition",
    "-c",
    type=str,
    help="CEL based condition.",
    required=True,
    default="",
)
@pass_info
def create(
    info: Info,
    name: str,
    description: str,
    priority: int,
    pre: bool,
    attribute: str,
    regex: str,
    condition: str,
):
    """Create a extraction rule."""
    response = make_keep_request(
        "POST",
        info.keep_api_url + "/extraction",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json={
            "name": name,
            "description": description,
            "priority": priority,
            "pre": pre,
            "attribute": attribute,
            "regex": regex,
            "condition": condition,
        },
    )

    # Check the response
    if response.ok:
        click.echo(
            click.style(f"Extraction rule {name} created successfully", bold=True)
        )
    else:
        click.echo(
            click.style(
                f"Error creating extraction rule {name}: {response.text}",
                bold=True,
            )
        )


@extraction.command(name="delete")
@click.option(
    "--extraction-id",
    type=int,
    help="The ID of the extraction to delete.",
    required=True,
)
@pass_info
def delete_extraction(info: Info, extraction_id: int):
    """Delete a extraction with a specified ID."""

    # Delete the extraction with the specified ID
    response = make_keep_request(
        "DELETE",
        info.keep_api_url + f"/extraction/{extraction_id}",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )

    # Check the response
    if response.ok:
        click.echo(
            click.style(
                f"Extraction rule {extraction_id} deleted successfully", bold=True
            )
        )
    else:
        click.echo(
            click.style(
                f"Error deleting extraction rule {extraction_id}: {response.text}",
                bold=True,
            )
        )


@cli.group()
@pass_info
def provider(info: Info):
    """Manage providers."""
    pass


@provider.command(name="build_cache", help="Output providers cache for future use")
def build_cache():
    class ProviderEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, ProviderScope):
                dct = o.__dict__
                dct.pop("__pydantic_initialised__", None)
                return dct
            elif isinstance(o, _MISSING_TYPE):
                return None
            return o.dict()

    logger.info("Building providers cache")
    providers_cache = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    with open("providers_cache.json", "w") as f:
        json.dump(providers_cache, f, cls=ProviderEncoder)
    logger.info(
        "Providers cache built successfully", extra={"file": "providers_cache.json"}
    )


@provider.command(name="list")
@click.option(
    "--available",
    "-a",
    default=False,
    is_flag=True,
    help="List provider that you can install.",
)
@pass_info
def list_providers(info: Info, available: bool):
    """List providers."""
    resp = make_keep_request(
        "GET",
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
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/providers",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting providers: {resp.text}")

    available_providers = resp.json().get("providers")

    provider = [p for p in available_providers if p.get("type") == provider_type]
    if not provider:
        click.echo(
            click.style(
                f"Provider {provider_type} not found, you can open an issue and we will create it within a blink of an eye https://github.com/keephq/keep",
                bold=True,
            )
        )
        return
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
            param_as_flag = f"--{param.replace('_', '-')}"
            table.add_row(
                [
                    provider_type,
                    param_as_flag,
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
    ctx.args
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
    resp = make_keep_request(
        "POST",
        info.keep_api_url + "/providers/install",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=provider_install_payload,
    )
    if not resp.ok:
        # installation failed because the credentials are invalid
        if resp.status_code == 412:
            click.echo(
                click.style("Failed to install provider: invalid scopes", bold=True)
            )
            table = PrettyTable()
            table.field_names = ["Scope Name", "Status"]
            for scope, value in resp.json().get("detail").items():
                table.add_row([scope, value])
            print(table)
        else:
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


@provider.command()
@click.argument(
    "provider_id",
    required=False,
)
@click.pass_context
def delete(ctx, provider_id):
    info = ctx.ensure_object(Info)
    dummy_provider_type = "dummy"
    resp = make_keep_request(
        "DELETE",
        info.keep_api_url + f"/providers/{dummy_provider_type}/{provider_id}",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        if resp.status_code == 404:
            click.echo(
                click.style(f"Provider {provider_id} not found", bold=True, fg="red")
            )
        else:
            click.echo(
                click.style(
                    f"Error deleting provider {provider_id}: {resp.text}", bold=True
                )
            )
    else:
        click.echo(
            click.style(f"Provider {provider_id} deleted successfully", bold=True)
        )


def _get_alert_by_fingerprint(keep_url, api_key, fingerprint: str):
    """Get an alert by fingerprint."""
    resp = make_keep_request(
        "GET",
        keep_url + f"/alerts/{fingerprint}",
        headers={"x-api-key": api_key, "accept": "application/json"},
    )
    return resp


@cli.group()
@pass_info
def alert(info: Info):
    """Manage alerts."""
    pass


@alert.command(name="get")
@click.argument(
    "fingerprint",
    required=True,
    type=str,
)
@pass_info
def get_alert(info: Info, fingerprint: str):
    """Get an alert by fingerprint."""
    resp = _get_alert_by_fingerprint(info.keep_api_url, info.api_key, fingerprint)
    if not resp.ok:
        raise Exception(f"Error getting alert: {resp.text}")
    else:
        alert = resp.json()
        print(json.dumps(alert, indent=4))


@alert.command(name="list")
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
def list_alerts(info: Info, filter: typing.List[str], export: bool):
    """List alerts."""
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/alerts?sync=true",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting providers: {resp.text}")

    alerts = resp.json()

    # aggregate by fingerprint
    aggregated_alerts = OrderedDict()
    for alert in sorted(alerts, key=lambda x: x["lastReceived"]):
        if alert["fingerprint"] not in aggregated_alerts:
            aggregated_alerts[alert["fingerprint"]] = alert

    alerts = aggregated_alerts.values()

    if len(alerts) == 0:
        click.echo(click.style("No alerts found.", bold=True))
        return

    # Apply all provided filters
    for filt in filter:
        key, value = filt.split("=")
        _alerts = []
        for alert in alerts:
            val = alert.get(key)
            if isinstance(val, list):
                if value in val:
                    _alerts.append(alert)
            else:
                if val == value:
                    _alerts.append(alert)
        alerts = _alerts

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
        "Severity",
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
                alert["severity"],
                alert["status"],
                alert["environment"],
                alert["service"],
                alert["source"],
                alert["lastReceived"],
            ]
        )
    print(table)


@alert.command()
@click.option(
    "--fingerprint", required=True, help="The fingerprint of the alert to enrich."
)
@click.argument("params", nargs=-1, type=click.UNPROCESSED)
@pass_info
def enrich(info: Info, fingerprint, params):
    """Enrich an alert."""

    # Convert arguments to dictionary
    for param in params:
        # validate the all params are key/value pairs
        if len(param.split("=")) != 2:
            raise click.BadArgumentUsage("Parameters must be given in key=value pairs")

    params_dict = {param.split("=")[0]: param.split("=")[1] for param in params}
    params_dict = {
        "fingerprint": fingerprint,
        "enrichments": params_dict,
    }
    # Make the API request
    resp = make_keep_request(
        "POST",
        f"{info.keep_api_url}/alerts/enrich",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=params_dict,
    )

    # Check the response
    if not resp.ok:
        click.echo(
            click.style(f"Error enriching alert {fingerprint}: {resp.text}", bold=True)
        )
    else:
        click.echo(click.style(f"Alert {fingerprint} enriched successfully", bold=True))


@alert.command()
@click.option(
    "--provider-type",
    "-p",
    type=click.Path(exists=False),
    help="The type of the provider which will be used to simulate the alert.",
    required=True,
)
@click.argument("params", nargs=-1, type=click.UNPROCESSED)
@pass_info
def simulate(info: Info, provider_type: str, params: list[str]):
    """Simulate an alert."""
    click.echo(click.style("Simulating alert", bold=True))
    try:
        provider = ProvidersFactory.get_provider_class(provider_type)
    except Exception as e:
        click.echo(click.style(f"No such provuder: {e}", bold=True))
        return

    try:
        alert = provider.simulate_alert()
    except Exception:
        click.echo(click.style("Provider does not support alert simulation", bold=True))
        return
    # override the alert with the provided params
    for param in params:
        key, value = param.split("=")
        # if the param contains "."
        if "." in key:
            # split the key by "." and set the value in the alert
            keys = key.split(".")
            alert[keys[0]][keys[1]] = value
        else:
            alert[key] = value
    click.echo("Simulated alert:")
    click.echo(json.dumps(alert, indent=4))
    # send the alert to the server
    resp = make_keep_request(
        "POST",
        info.keep_api_url + f"/alerts/event/{provider_type}",
        headers={"x-api-key": info.api_key, "accept": "application/json"},
        json=alert,
    )
    if not resp.ok:
        click.echo(click.style(f"Error simulating alert: {resp.text}", bold=True))
    else:
        click.echo(click.style("Alert simulated successfully", bold=True))


@cli.group()
@pass_info
def auth(info: Info):
    """Manage auth."""
    pass


# global token will be populated in the callback
token = None


@auth.command()
@pass_info
def login(info: Info):
    # first, prepare the oauth2 session:
    import os
    import threading
    import time
    import webbrowser

    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from requests_oauthlib import OAuth2Session

    app = FastAPI()

    @app.get("/callback")
    def callback(code: str, state: str):
        global token
        token_url = "https://auth.keephq.dev/oauth/token"
        token = oauth_session.fetch_token(
            token_url,
            code=code,
            client_secret="",
            include_client_id=True,
            authorization_response=redirect_uri,
        )
        print("Got the token")
        return PlainTextResponse(
            "Authenticated successfully, you can close this tab now, Keep rulezzz!"
        )

    # We needed a way to run a server without blocking the main thread:
    #   https://github.com/encode/uvicorn/discussions/1103#discussioncomment-1389875
    class UvicornServer:
        def __init__(self):
            super().__init__()

        def start(self):
            # Define the FastAPI app running logic here
            uvicorn.run(app, host="127.0.0.1", port=8085, log_level="critical")

    # These are the public client_id of KeepHQ auth0
    # If you have your own identity provider, we'll need to implement to flow
    client_id = os.getenv("KEEP_OAUTH_CLIENT_ID", "P7zzubZGLNe8BQ4HRzvrhT5qPgRFa0BL")
    authorization_base_url = os.getenv(
        "KEEP_OAUTH_AUTHORIZATION_BASE_URL", "https://auth.keephq.dev/authorize"
    )
    scope = ["openid", "profile", "email"]
    redirect_uri = "http://localhost:8085/callback"
    oauth_session = OAuth2Session(client_id, scope=scope, redirect_uri=redirect_uri)
    # now that we have the state parameter, we can start the fast api server
    # start the server on another process
    server_thread = threading.Thread(target=UvicornServer().start)
    server_thread.start()
    # now, open the browser and wait for the authentication
    webbrowser.open(oauth_session.authorization_url(authorization_base_url)[0])
    # Now wait for the callback
    timeout = 60 * 2  # 2 minutes
    times = 0
    time_start = time.time()
    while not token:
        if time.time() - time_start > timeout:
            print("Timeout waiting for callback")
            # kill the server
            os._exit(1)
        # print every 15 seconds
        if times % 15 == 0:
            print("Still waiting for callback")
        time.sleep(1)

    # Ok, we got the token from the oauth2 flow, now let's get a permanent api key
    print("Got the token, getting the api key")
    id_token = token["id_token"]
    api_key_resp = make_keep_request(
        "GET",
        info.keep_api_url + "/settings/apikey",
        headers={"accept": "application/json", "Authorization": f"Bearer {id_token}"},
    )
    if not api_key_resp.ok:
        print(f"Error getting api key: {api_key_resp.text}")
        # kill the server
        os._exit(2)

    api_key = api_key_resp.json().get("apiKey")
    # keep it in the config file
    with open(f"{get_default_conf_file_path()}", "w") as f:
        f.write(f"api_key: {api_key}\n")
    # Authenticated successfully
    print("Authenticated successfully!")
    # Check that we can get whoami
    resp = make_keep_request(
        "GET",
        info.keep_api_url + "/whoami",
        headers={"x-api-key": api_key, "accept": "application/json"},
    )
    if not resp.ok:
        raise Exception(f"Error getting whoami: {resp.text}")
    print("Authenticated to Keep successfully!")
    print(resp.json())
    # kills the server also, great success
    os._exit(0)


if __name__ == "__main__":
    cli(auto_envvar_prefix="KEEP")
