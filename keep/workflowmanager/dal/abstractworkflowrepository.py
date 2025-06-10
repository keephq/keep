from abc import ABC, abstractmethod
import io
import logging
import os
import random
import uuid
from typing import List, Tuple

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
    get_workflow_execution_with_logs,
)
from keep.workflowmanager.dal.sql.workflows import (
    WorkflowWithLastExecutions,
    get_workflows_with_last_executions_v2,
)
from keep.api.models.db.workflow import Workflow as WorkflowModel
from keep.api.models.query import QueryDto
from keep.api.models.workflow import PreparsedWorkflowDTO, ProviderDTO
from keep.functions import cyaml
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from keep.workflowmanager.workflow import Workflow
from sqlalchemy.exc import NoResultFound


class WorkflowRepository(ABC):
    @abstractmethod
    def add_or_update_workflow(
        self,
        id: str,
        name: str,
        tenant_id: str,
        description: str | None,
        created_by: str,
        interval: int | None,
        workflow_raw: str,
        is_disabled: bool,
        updated_by: str,
        provisioned: bool = False,
        provisioned_file: str | None = None,
        force_update: bool = False,
        is_test: bool = False,
        lookup_by_name: bool = False,
    ) -> WorkflowDalModel:
        pass

    @abstractmethod
    def delete_workflow(self, tenant_id, workflow_id):
        pass

    @abstractmethod
    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    @abstractmethod
    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        pass

    @abstractmethod
    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
        pass

    @abstractmethod
    def get_all_workflows_yamls(self, tenant_id: str):
        pass

    @abstractmethod
    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        pass

    @abstractmethod
    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        pass

    @abstractmethod
    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        pass

    @abstractmethod
    def get_workflows_with_last_executions_v2(
        self,
        tenant_id: str,
        cel: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_dir: str,
        fetch_last_executions: int = 15,
    ) -> Tuple[list[WorkflowWithLastExecutions], int]:
        pass
