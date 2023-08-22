import io
import logging
import os
import typing
import uuid

import requests
import validators
import yaml
from fastapi import HTTPException

from keep.api.core.db import add_workflow, delete_workflow, get_workflow, get_workflows
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
        workflow = add_workflow(
            id=str(uuid.uuid4()),
            name=workflow_id,
            tenant_id=tenant_id,
            description=workflow.get("description"),
            created_by=created_by,
            interval=workflow.get("interval", 0),
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
        self._load_providers_from_installed_providers(tenant_id)
        workflow = self.parser.parse(workflow_yaml)
        if workflow:
            return workflow
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found",
            )

    def get_all_workflows(self, tenant_id: str) -> list[Workflow]:
        # list all tenant's workflows
        workflows = get_workflows(tenant_id)
        return workflows

    def get_workflows(
        self, workflow_path: str | tuple[str], providers_file: str = None
    ) -> list[Workflow]:
        # get specific workflows, the original interface
        # to interact with workflows
        workflows = []
        if isinstance(workflow_path, tuple):
            for workflow_url in workflow_path:
                workflow_yaml = self._parse_workflow_to_dict(workflow_url)
                workflows.extend(self.parser.parse(workflow_yaml, providers_file))
        elif os.path.isdir(workflow_path):
            workflows.extend(
                self._get_workflows_from_directory(workflow_path, providers_file)
            )
        else:
            workflow_yaml = self._parse_workflow_to_dict(workflow_path)
            workflows = self.parser.parse(workflow_yaml, providers_file)

        return workflows

    def _get_workflows_from_directory(
        self, workflows_dir: str, providers_file: str = None
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
                        self.parser.parse(parsed_workflow_yaml, providers_file)
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

    def _load_providers_from_installed_providers(self, tenant_id: str):
        # TODO: should be refactored and moved to ProvidersManager or something
        # Load installed providers
        all_providers = ProvidersFactory.get_all_providers()
        installed_providers = ProvidersFactory.get_installed_providers(
            tenant_id=tenant_id, all_providers=all_providers
        )
        for provider in installed_providers:
            self.logger.info(f"Loading provider {provider}")
            try:
                provider_name = provider.details.get("name")
                context_manager = ContextManager.get_instance(tenant_id=tenant_id)
                context_manager.providers_context[provider.id] = provider.details
                # map also the name of the provider, not only the id
                # so that we can use the name to reference the provider
                context_manager.providers_context[provider_name] = provider.details
                self.logger.info(f"Provider {provider.id} loaded successfully")
            except Exception as e:
                self.logger.error(
                    f"Error loading provider {provider.id}", extra={"exception": e}
                )
