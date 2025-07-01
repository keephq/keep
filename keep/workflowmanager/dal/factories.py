import os
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.elasticsearch.create import (
    create_elasticsearch_workflow_repository,
)
from keep.workflowmanager.dal.sql.sqlworkflowrepository import (
    SqlWorkflowRepository,
)


WORKFLOW_ENGINE_USE_ELASTICSEARCH = (
    os.environ.get("WORKFLOW_ENGINE_USE_ELASTICSEARCH", "false").lower() == "true"
)

if WORKFLOW_ENGINE_USE_ELASTICSEARCH:
    db_or_elastic = "elastic"
else:
    db_or_elastic = "db"


def create_workflow_repository() -> WorkflowRepository:
    if db_or_elastic == "db":
        return SqlWorkflowRepository()

    if db_or_elastic == "elastic":
        return create_elasticsearch_workflow_repository()

    raise NotImplementedError(
        f"Unsupported workflow repository type: '{db_or_elastic}'. "
        "Only 'db' and 'elastic' are supported."
    )
