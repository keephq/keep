from elasticsearch.dsl import Document, Text, Date, Keyword, Object


class WorkflowExecutionLogDoc(Document):
    workflow_execution_id = Keyword()
    timestamp = Date()
    message = Text()
    context = Object()

    class Index:
        name = "workflow-engine-workflow-execution-log-docs"
