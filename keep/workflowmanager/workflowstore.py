import io
import logging
import os
import typing
import uuid

import requests
import validators
import yaml
from fastapi import HTTPException

from keep.api.core.db import (
    add_workflow,
    delete_workflow,
    get_workflow,
    get_workflows_with_last_execution,
)
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.storagemanager.storagemanagerfactory import StorageManagerFactory
from keep.workflowmanager.workflow import Workflow


class WorkflowStore:
    # TODO: workflow store should be persistent using database and not only "filesystem"
    #       e.g. we should be able to get workflows from a database

    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def create_workflow(self, tenant_id: str, created_by, workflow: dict):
        workflow_id = workflow.get("id")
        self.logger.info(f"Creating workflow {workflow_id}")
        interval = self.parser._parse_interval(workflow)
        workflow = add_workflow(
            id=str(uuid.uuid4()),
            name=workflow_id,
            tenant_id=tenant_id,
            description=workflow.get("description"),
            created_by=created_by,
            interval=interval,
            workflow_raw=yaml.dump(workflow),
        )
        self.logger.info(f"Workflow {workflow_id} created successfully")
        return workflow

    def delete_workflow(self, tenant_id, workflow_id):
        self.logger.info(f"Deleting workflow {workflow_id}")
        try:
            workflow = delete_workflow(tenant_id, workflow_id)
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"Workflow {workflow_id} not found"
            )

    def _parse_workflow_to_dict(self, workflow_path: str) -> dict:
        """
        Parse an workflow to a dictionary from either a file or a URL.

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

    def get_workflow(self, tenant_id: str, workflow_id: str) -> Workflow:
        workflow = get_workflow(tenant_id, workflow_id)
        workflow_yaml = yaml.safe_load(workflow)
        workflow = self.parser.parse(tenant_id, workflow_yaml)
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

    def get_all_workflows(self, tenant_id: str) -> list[Workflow]:
        # list all tenant's workflows
        workflows = get_workflows_with_last_execution(tenant_id)
        return workflows

    def get_workflows_from_path(
        self, tenant_id, workflow_path: str | tuple[str], providers_file: str = None
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
                    self.parser.parse(tenant_id, workflow_yaml, providers_file)
                )
        elif os.path.isdir(workflow_path):
            workflows.extend(
                self._get_workflows_from_directory(
                    tenant_id, workflow_path, providers_file
                )
            )
        else:
            workflow_yaml = self._parse_workflow_to_dict(workflow_path)
            workflows = self.parser.parse(tenant_id, workflow_yaml, providers_file)

        return workflows

    def _get_workflows_from_directory(
        self, tenant_id, workflows_dir: str, providers_file: str = None
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
                            tenant_id, parsed_workflow_yaml, providers_file
                        )
                    )
                    self.logger.info(f"Workflow from {file} fetched successfully")
                except Exception as e:
                    self.logger.error(
                        f"Error parsing workflow from {file}", extra={"exception": e}
                    )
        return workflows

    def _read_workflow_from_stream(self, stream) -> dict:
        """
        Parse an workflow from an IO stream.

        Args:
            stream (IOStream): The stream to read from

        Raises:
            e: If the stream is not a valid YAML

        Returns:
            dict: Dictionary with the workflow information
        """
        self.logger.debug("Parsing workflow")
        try:
            workflow = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing workflow: {e}")
            raise e
        return workflow
