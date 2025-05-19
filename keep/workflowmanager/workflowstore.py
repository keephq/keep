import io
import logging
import os
import random
import uuid
from typing import Tuple

import celpy
import requests
import validators
from fastapi import HTTPException

from keep.api.core.db import (
    add_or_update_workflow,
    delete_workflow,
    delete_workflow_by_provisioned_file,
    get_all_provisioned_workflows,
    get_all_workflows,
    get_all_workflows_yamls,
    get_workflow_by_id,
    get_workflow_execution,
)
from keep.api.core.workflows import get_workflows_with_last_executions_v2
from keep.api.models.db.workflow import Workflow as WorkflowModel
from keep.api.models.query import QueryDto
from keep.api.models.workflow import PreparsedWorkflowDTO, ProviderDTO
from keep.functions import cyaml
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.workflow import Workflow


class WorkflowStore:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)
        self.celpy_env = celpy.Environment()

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ):
        return get_workflow_execution(tenant_id, workflow_execution_id, is_test_run)

    def create_workflow(
        self, tenant_id: str, created_by, workflow: dict, force_update: bool = True
    ):
        workflow_id = workflow.get("id")
        self.logger.info(f"Creating workflow {workflow_id}")
        interval = self.parser.parse_interval(workflow)
        if not workflow.get("name"):  # workflow name is None or empty string
            workflow_name = workflow_id
            workflow["name"] = workflow_name
        else:
            workflow_name = workflow.get("name")

        workflow_db = add_or_update_workflow(
            id=str(uuid.uuid4()),
            name=workflow_name,
            tenant_id=tenant_id,
            description=workflow.get("description"),
            created_by=created_by,
            updated_by=created_by,
            interval=interval,
            is_disabled=Parser.parse_disabled(workflow),
            workflow_raw=cyaml.dump(workflow, width=99999),
            force_update=force_update,
        )
        self.logger.info(
            f"Workflow {workflow_db.id}, {workflow_db.revision} created successfully"
        )
        return workflow_db

    def delete_workflow(self, tenant_id, workflow_id):
        self.logger.info(f"Deleting workflow {workflow_id}")
        workflow = get_workflow_by_id(tenant_id, workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404, detail=f"Workflow {workflow_id} not found"
            )
        if workflow.provisioned:
            raise HTTPException(403, detail="Cannot delete a provisioned workflow")
        try:
            delete_workflow(tenant_id, workflow_id)
        except Exception as e:
            self.logger.exception(f"Error deleting workflow {workflow_id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete workflow {workflow_id}"
            )

    def _parse_workflow_to_dict(self, workflow_path: str) -> dict:
        """
        Parse a workflow to a dictionary from either a file or a URL.

        Args:
            workflow_path (str): a URL or a file path

        Returns:
            dict: Dictionary with the workflow information
        """
        self.logger.debug("Parsing workflow")
        # If the workflow is a URL, get the workflow from the URL
        if validators.url(workflow_path) is True:
            response = requests.get(workflow_path)
            return self._read_workflow_from_stream(io.StringIO(response.text))
        else:
            # else, get the workflow from the file
            with open(workflow_path, "r") as file:
                return self._read_workflow_from_stream(file)

    def get_raw_workflow(self, tenant_id: str, workflow_id: str) -> str:
        workflow = get_workflow_by_id(tenant_id, workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found",
            )
        return self.format_workflow_yaml(workflow.workflow_raw)

    def get_workflow(self, tenant_id: str, workflow_id: str) -> Workflow:
        workflow = get_workflow_by_id(tenant_id, workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found",
            )
        workflow_yaml = cyaml.safe_load(workflow.workflow_raw)
        workflow = self.parser.parse(
            tenant_id,
            workflow_yaml,
            workflow_db_id=workflow.id,
            workflow_revision=workflow.revision,
            is_test=workflow.is_test,
        )
        if len(workflow) > 1:
            raise HTTPException(
                status_code=500,
                detail=f"More than one workflow with id {workflow_id} found",
            )
        elif workflow:
            return workflow[0]
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found",
            )

    def get_workflow_from_dict(self, tenant_id: str, workflow_dict: dict) -> Workflow:
        logging.info("Parsing workflow from dict", extra={"workflow": workflow_dict})
        workflow = self.parser.parse(tenant_id, workflow_dict)
        if workflow:
            return workflow[0]
        else:
            raise HTTPException(
                status_code=500,
                detail="Unable to parse workflow from dict",
            )

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> list[WorkflowModel]:
        # list all tenant's workflows
        workflows = get_all_workflows(tenant_id, exclude_disabled)
        return workflows

    def get_all_workflows_with_last_execution(
        self,
        tenant_id: str,
        cel: str = None,
        limit: int = None,
        offset: int = None,
        sort_by: str = None,
        sort_dir: str = None,
        session=None,
    ):
        # list all tenant's workflows
        return get_workflows_with_last_executions_v2(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=15,
            session=session,
        )

    def get_all_workflows_yamls(self, tenant_id: str) -> list[str]:
        # list all tenant's workflows yamls (Workflow.workflow_raw)
        return list(get_all_workflows_yamls(tenant_id))

    def get_workflows_from_path(
        self,
        tenant_id,
        workflow_path: str | tuple[str],
        providers_file: str = None,
        actions_file: str = None,
    ) -> list[Workflow]:
        """Backward compatibility method to get workflows from a path.

        Args:
            workflow_path (str | tuple[str]): _description_
            providers_file (str, optional): _description_. Defaults to None.

        Returns:
            list[Workflow]: _description_
        """
        # get specific workflows, the original interface
        # to interact with workflows
        workflows = []
        if isinstance(workflow_path, tuple):
            for workflow_url in workflow_path:
                workflow_yaml = self._parse_workflow_to_dict(workflow_url)
                workflows.extend(
                    self.parser.parse(
                        tenant_id, workflow_yaml, providers_file, actions_file
                    )
                )
        elif os.path.isdir(workflow_path):
            workflows.extend(
                self._get_workflows_from_directory(
                    tenant_id, workflow_path, providers_file, actions_file
                )
            )
        else:
            workflow_yaml = self._parse_workflow_to_dict(workflow_path)
            workflows = self.parser.parse(
                tenant_id, workflow_yaml, providers_file, actions_file
            )

        return workflows

    def _get_workflows_from_directory(
        self,
        tenant_id,
        workflows_dir: str,
        providers_file: str = None,
        actions_file: str = None,
    ) -> list[Workflow]:
        """
        Run workflows from a directory.

        Args:
            workflows_dir (str): A directory containing workflows yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        workflows = []
        for file in os.listdir(workflows_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                self.logger.info(f"Getting workflows from {file}")
                parsed_workflow_yaml = self._parse_workflow_to_dict(
                    os.path.join(workflows_dir, file)
                )
                try:
                    workflows.extend(
                        self.parser.parse(
                            tenant_id,
                            parsed_workflow_yaml,
                            providers_file,
                            actions_file,
                        )
                    )
                    self.logger.info(f"Workflow from {file} fetched successfully")
                except Exception as e:
                    print(e)
                    self.logger.error(
                        f"Error parsing workflow from {file}", extra={"exception": e}
                    )
        return workflows

    @staticmethod
    def format_workflow_yaml(yaml_string: str) -> str:
        yaml_content = cyaml.safe_load(yaml_string)
        if "workflow" in yaml_content:
            yaml_content = yaml_content["workflow"]
        # backward compatibility
        elif "alert" in yaml_content:
            yaml_content = yaml_content["alert"]
        valid_workflow_yaml = {"workflow": yaml_content}
        return cyaml.dump(valid_workflow_yaml, width=99999)

    @staticmethod
    def pre_parse_workflow_yaml(yaml_content):
        parser = Parser()

        if "workflow" in yaml_content:
            yaml_content = yaml_content["workflow"]
        # backward compatibility
        elif "alert" in yaml_content:
            yaml_content = yaml_content["alert"]

        workflow_name = yaml_content.get("name") or yaml_content.get("id")
        if not workflow_name:
            raise ValueError(f"Workflow {yaml_content} does not have a name or id")

        workflow_id = str(uuid.uuid4())
        workflow_description = yaml_content.get("description")
        workflow_interval = parser.parse_interval(yaml_content)
        workflow_disabled = parser.parse_disabled(yaml_content)

        return PreparsedWorkflowDTO(
            id=workflow_id,
            name=workflow_name,
            description=workflow_description,
            interval=workflow_interval,
            disabled=workflow_disabled,
        )

    @staticmethod
    def provision_workflows(
        tenant_id: str,
    ) -> list[Workflow]:
        """
        Provision workflows from a directory or env variable.

        Args:
            tenant_id (str): The tenant ID.

        Returns:
            list[Workflow]: A list of provisioned Workflow objects.
        """
        logger = logging.getLogger(__name__)
        provisioned_workflows = []

        provisioned_workflows_dir = os.environ.get("KEEP_WORKFLOWS_DIRECTORY")
        provisioned_workflow_yaml = os.environ.get("KEEP_WORKFLOW")

        # Get all existing provisioned workflows
        logger.info("Getting all already provisioned workflows")
        provisioned_workflows = get_all_provisioned_workflows(tenant_id)
        logger.info(f"Found {len(provisioned_workflows)} provisioned workflows")

        if not (provisioned_workflows_dir or provisioned_workflow_yaml):
            logger.info("No workflows for provisioning found")

            if provisioned_workflows:
                logger.info("Found existing provisioned workflows, deleting them")
                for workflow in provisioned_workflows:
                    logger.info(f"Deprovisioning workflow {workflow.id}")
                    delete_workflow(tenant_id, workflow.id)
                    logger.info(f"Workflow {workflow.id} deprovisioned successfully")
            return []

        if (
            provisioned_workflows_dir is not None
            and provisioned_workflow_yaml is not None
        ):
            raise Exception(
                "Workflows provisioned via env var and directory at the same time. Please choose one."
            )

        if provisioned_workflows_dir is not None and not os.path.isdir(
            provisioned_workflows_dir
        ):
            raise FileNotFoundError(
                f"Directory {provisioned_workflows_dir} does not exist"
            )

        ### Provisioning from env var
        if provisioned_workflow_yaml is not None:
            logger.info("Provisioning workflow from env var")
            pre_parsed_workflow = None
            try:
                workflow_yaml = cyaml.safe_load(provisioned_workflow_yaml)
                pre_parsed_workflow = WorkflowStore.pre_parse_workflow_yaml(
                    workflow_yaml
                )
            except ValueError as e:
                logger.error(
                    "Error provisioning workflow from env var: yaml is invalid",
                    extra={"exception": e},
                )

            try:
                # Un-provisioning other workflows.
                for workflow in provisioned_workflows:
                    if (
                        not pre_parsed_workflow
                        or not workflow.name == pre_parsed_workflow.name
                    ):
                        if not pre_parsed_workflow:
                            logger.info(
                                f"Deprovisioning workflow {workflow.id} as no workflows to provision"
                            )
                        else:
                            logger.info(
                                f"Deprovisioning workflow {workflow.id} as its id doesn't match the provisioned workflow provided in the env"
                            )
                        delete_workflow(tenant_id, workflow.id)
                        logger.info(
                            f"Workflow {workflow.id} deprovisioned successfully"
                        )

                if not pre_parsed_workflow:
                    logger.info("No workflows to provision")
                    return []

                logger.info(
                    f"Provisioning workflow {pre_parsed_workflow.id} from env var"
                )

                add_or_update_workflow(
                    id=pre_parsed_workflow.id,
                    name=pre_parsed_workflow.name,
                    tenant_id=tenant_id,
                    description=pre_parsed_workflow.description,
                    created_by="system",
                    updated_by="system",
                    interval=pre_parsed_workflow.interval,
                    is_disabled=pre_parsed_workflow.disabled,
                    workflow_raw=cyaml.dump(workflow_yaml, width=99999),
                    provisioned=True,
                    provisioned_file=None,
                )
                provisioned_workflows.append(workflow_yaml)
                logger.info("Workflow provisioned successfully")
            except Exception as e:
                logger.error(
                    "Error provisioning workflow from env var",
                    extra={"exception": e},
                )

        ### Provisioning from the directory
        if provisioned_workflows_dir is not None:

            logger.info(
                f"Provisioning workflows from directory {provisioned_workflows_dir}"
            )

            # Check for workflows that are no longer in the directory or outside the workflows_dir and delete them
            for workflow in provisioned_workflows:
                if (
                    workflow.provisioned_file is None
                    or not os.path.exists(workflow.provisioned_file)
                    or not provisioned_workflows_dir.endswith(
                        os.path.commonpath(
                            [provisioned_workflows_dir, workflow.provisioned_file]
                        )
                    )
                ):
                    logger.info(
                        f"Deprovisioning workflow {workflow.id} as its file no longer exists or is outside the workflows directory"
                    )
                    delete_workflow_by_provisioned_file(
                        tenant_id, workflow.provisioned_file
                    )
                    logger.info(f"Workflow {workflow.id} deprovisioned successfully")

            # Provision new workflows from the directory
            for file in os.listdir(provisioned_workflows_dir):
                if file.endswith((".yaml", ".yml")):
                    logger.info(f"Provisioning workflow from {file}")
                    workflow_path = os.path.join(provisioned_workflows_dir, file)

                    try:
                        with open(workflow_path, "r") as yaml_file:
                            workflow_yaml = cyaml.safe_load(yaml_file.read())
                            pre_parsed_workflow = WorkflowStore.pre_parse_workflow_yaml(
                                workflow_yaml
                            )
                        add_or_update_workflow(
                            id=pre_parsed_workflow.id,
                            name=pre_parsed_workflow.name,
                            tenant_id=tenant_id,
                            description=pre_parsed_workflow.description,
                            created_by="system",
                            updated_by="system",
                            interval=pre_parsed_workflow.interval,
                            is_disabled=pre_parsed_workflow.disabled,
                            workflow_raw=cyaml.dump(workflow_yaml, width=99999),
                            provisioned=True,
                            provisioned_file=workflow_path,
                        )
                        provisioned_workflows.append(workflow_yaml)
                        logger.info(f"Workflow from {file} provisioned successfully")
                    except Exception as e:
                        logger.error(
                            f"Error provisioning workflow from {file}",
                            extra={"exception": e},
                        )
                else:
                    logger.info(f"Skipping file {file} as it is not a YAML file")

        return provisioned_workflows

    def _read_workflow_from_stream(self, stream) -> dict:
        """
        Parse a workflow from an IO stream.

        Args:
            stream (IOStream): The stream to read from

        Raises:
            e: If the stream is not a valid YAML

        Returns:
            dict: Dictionary with the workflow information
        """
        self.logger.debug("Parsing workflow")
        try:
            workflow = cyaml.safe_load(stream)
        except cyaml.YAMLError as e:
            self.logger.error(f"Error parsing workflow: {e}")
            raise e
        return workflow

    def get_random_workflow_templates(
        self, tenant_id: str, workflows_dir: str, limit: int
    ) -> list[dict]:
        """
        Get random workflows from a directory.
        Args:
            tenant_id (str): The tenant to which the workflows belong.
            workflows_dir (str): A directory containing workflows yamls.
            limit (int): The number of workflows to return.

        Returns:
            List[dict]: A list of workflows
        """
        if not os.path.isdir(workflows_dir):
            raise FileNotFoundError(f"Directory {workflows_dir} does not exist")

        workflow_yaml_files = [
            f for f in os.listdir(workflows_dir) if f.endswith((".yaml", ".yml"))
        ]
        if not workflow_yaml_files:
            raise FileNotFoundError(f"No workflows found in directory {workflows_dir}")

        random.shuffle(workflow_yaml_files)
        workflows = []
        count = 0
        for file in workflow_yaml_files:
            if count == limit:
                break
            try:
                file_path = os.path.join(workflows_dir, file)
                workflow_yaml = self._parse_workflow_to_dict(file_path)
                if "workflow" in workflow_yaml:
                    workflow_yaml["name"] = workflow_yaml["workflow"]["id"]
                    workflow_yaml["workflow_raw"] = cyaml.dump(workflow_yaml)
                    workflow_yaml["workflow_raw_id"] = workflow_yaml["workflow"]["id"]
                    workflows.append(workflow_yaml)
                    count += 1

                self.logger.info(f"Workflow from {file} fetched successfully")
            except Exception as e:
                self.logger.error(
                    f"Error parsing or fetching workflow from {file}: {e}"
                )
        return workflows

    def query_workflow_templates(
        self, tenant_id: str, workflows_dir: str, query: QueryDto
    ) -> Tuple[list[dict], int]:
        """
        Get random workflows from a directory.
        Args:
            tenant_id (str): The tenant to which the workflows belong.
            workflows_dir (str): A directory containing workflows yamls.
            limit (int): The number of workflows to return.

        Returns:
            List[dict]: A list of workflows
        """
        if not os.path.isdir(workflows_dir):
            raise FileNotFoundError(f"Directory {workflows_dir} does not exist")

        workflow_yaml_files = [
            f for f in os.listdir(workflows_dir) if f.endswith((".yaml", ".yml"))
        ]
        if not workflow_yaml_files:
            raise FileNotFoundError(f"No workflows found in directory {workflows_dir}")

        workflows = []

        for file in workflow_yaml_files:
            try:
                file_path = os.path.join(workflows_dir, file)
                workflow_yaml = self._parse_workflow_to_dict(file_path)
                if "workflow" in workflow_yaml:
                    workflow_yaml["name"] = workflow_yaml["workflow"]["id"]
                    workflow_yaml["workflow_raw"] = cyaml.dump(workflow_yaml)
                    workflow_yaml["workflow_raw_id"] = workflow_yaml["workflow"]["id"]

                    if not query.cel:
                        workflows.append(workflow_yaml)
                        continue

                    ast = self.celpy_env.compile(query.cel)
                    prgm = self.celpy_env.program(ast)

                    activation = celpy.json_to_cel(
                        {
                            "name": workflow_yaml.get("workflow", {})
                            .get("name", None)
                            .lower(),
                            "description": workflow_yaml.get("workflow", {})
                            .get("description", "")
                            .lower(),
                        }
                    )
                    relevant = prgm.evaluate(activation)

                    if relevant:
                        workflows.append(workflow_yaml)

                self.logger.info(f"Workflow from {file} fetched successfully")
            except Exception as e:
                self.logger.error(
                    f"Error parsing or fetching workflow from {file}: {e}"
                )

        return workflows[query.offset : query.offset + query.limit], len(workflows)

    def get_workflow_meta_data(
        self,
        tenant_id: str,
        workflow: WorkflowModel | None,
        installed_providers_by_type: dict,
    ):
        providers_dto = []
        triggers = []

        # Early return if workflow is None
        if workflow is None:
            return providers_dto, triggers

        # Step 1: Load workflow YAML and handle potential parsing errors more thoroughly
        try:
            workflow_raw_data = workflow.workflow_raw
            if not isinstance(workflow_raw_data, str):
                self.logger.error(f"workflow_raw is not a string workflow: {workflow}")
                return providers_dto, triggers

            # Parse the workflow YAML safely
            workflow_yaml_dict = cyaml.safe_load(workflow_raw_data)
            if workflow_yaml_dict.get("workflow"):
                workflow_yaml_dict = workflow_yaml_dict.get("workflow")
            if not workflow_yaml_dict:
                self.logger.error(
                    f"Parsed workflow_yaml is empty or invalid: {workflow_yaml_dict}"
                )
                return providers_dto, triggers

        except Exception as e:
            # Improved logging to capture more details about the error
            self.logger.error(
                f"Failed to parse workflow in get_workflow_meta_data: {e}, workflow: {workflow}"
            )
            return (
                providers_dto,
                triggers,
            )  # Return empty providers and triggers in case of error

        try:
            providers = self.parser.get_providers_from_workflow_dict(workflow_yaml_dict)
        except Exception as e:
            self.logger.error(
                f"Failed to get providerts from workflow: {e}, workflow: {workflow}"
            )
            providers = []

        # Step 2: Process providers and add them to DTO
        for provider in providers:
            try:
                provider_data = installed_providers_by_type[provider.get("type")][
                    provider.get("name")
                ]
                provider_dto = ProviderDTO(
                    name=provider_data.name,
                    type=provider_data.type,
                    id=provider_data.id,
                    installed=True,
                )
                # add only if not already in the list
                if provider_data.id not in [p.id for p in providers_dto]:
                    providers_dto.append(provider_dto)
            except KeyError:
                # Handle case where the provider is not installed
                try:
                    conf = ProvidersFactory.get_provider_required_config(
                        provider.get("type")
                    )
                except ModuleNotFoundError:
                    self.logger.warning(
                        f"Non-existing provider in workflow: {provider.get('type')}"
                    )
                    conf = None

                # Handle providers based on whether they require config
                provider_dto = ProviderDTO(
                    name=provider.get("name"),
                    type=provider.get("type"),
                    id=None,
                    installed=(
                        conf is None
                    ),  # Consider it installed if no config is required
                )
                providers_dto.append(provider_dto)

        # Step 3: Extract triggers from workflow
        triggers = self.parser.get_triggers_from_workflow_dict(workflow_yaml_dict)

        return providers_dto, triggers

    @staticmethod
    def is_alert_rule_workflow(workflow_raw: dict):
        # checks if the workflow is an alert rule
        actions = workflow_raw.get("actions", [])
        for action in actions:
            # check if the action is a keep action
            is_keep_action = action.get("provider", {}).get("type") == "keep"
            if is_keep_action:
                # check if the keep action is an alert
                if "alert" in action.get("provider", {}).get("with", {}):
                    return True
        # if no keep action is found, return False
        return False
