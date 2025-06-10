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
from keep.api.core.workflows import get_workflows_with_last_executions_v2
from keep.api.models.db.workflow import Workflow as WorkflowModel
from keep.api.models.query import QueryDto
from keep.api.models.workflow import PreparsedWorkflowDTO, ProviderDTO
from keep.functions import cyaml
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.workflow import Workflow
from sqlalchemy.exc import NoResultFound


class SqlWorkflowRepository(WorkflowRepository):

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
    ) -> Workflow:
        return add_or_update_workflow(
            id=id,
            name=name,
            tenant_id=tenant_id,
            description=description,
            created_by=created_by,
            interval=interval,
            workflow_raw=workflow_raw,
            is_disabled=is_disabled,
            updated_by=updated_by,
            provisioned=provisioned,
            provisioned_file=provisioned_file,
            force_update=force_update,
            is_test=is_test,
            lookup_by_name=lookup_by_name,
        )

    def delete_workflow(self, tenant_id, workflow_id):
        delete_workflow(tenant_id=tenant_id, workflow_id=workflow_id)

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        delete_workflow_by_provisioned_file(
            tenant_id=tenant_id, provisioned_file=provisioned_file
        )

    def get_all_provisioned_workflows(self, tenant_id: str):
        return get_all_provisioned_workflows(tenant_id=tenant_id)

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[Workflow]:
        return get_all_workflows(tenant_id=tenant_id, exclude_disabled=exclude_disabled)

    def get_all_workflows_yamls(self, tenant_id: str):
        return get_all_workflows_yamls(tenant_id=tenant_id)

    def get_workflow_by_id(self, tenant_id: str, workflow_id: str):
        return get_workflow_by_id(tenant_id=tenant_id, workflow_id=workflow_id)

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ):
        return get_workflow_execution(
            tenant_id=tenant_id,
            workflow_execution_id=workflow_execution_id,
            is_test_run=is_test_run,
        )

    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ):
        return get_workflow_execution_with_logs(
            tenant_id=tenant_id,
            workflow_execution_id=workflow_execution_id,
            is_test_run=is_test_run,
        )
