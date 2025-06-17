from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.sql.sqlworkflowrepository import (
    SqlWorkflowRepository,
)

db_or_elastic = "db"


def create_workflow_repository() -> WorkflowRepository:
    if db_or_elastic == "db":
        return SqlWorkflowRepository()

    raise NotImplementedError(
        "Only db workflow repository is implemented, but db_or_elastic is set to something else."
    )
