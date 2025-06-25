from elasticsearch.dsl import Document, Text, Date, Integer, Keyword, Object
from keep.workflowmanager.dal.elasticsearch.models.client import es_client


class WorkflowExecutionLogDoc(Document):
    id = Integer()
    workflow_execution_id = Keyword()
    timestamp = Date()
    message = Text()
    context = Object()

    class Index:
        name = "workflow-engine-workflow-execution-log-docs"


WorkflowExecutionLogDoc.init(using=es_client)
