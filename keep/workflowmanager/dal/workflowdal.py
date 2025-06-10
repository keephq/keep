from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.sqlworkflowrepository import SqlWorkflowRepository


class WorkflowDal:
    def __init__(self, workflow_repository: WorkflowRepository):
        self.workflow_repository = workflow_repository

    @staticmethod
    def create_sql_dal():
        return WorkflowDal(workflow_repository=SqlWorkflowRepository())
