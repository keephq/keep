from elasticsearch.dsl import Document, Text, Date, Boolean, Integer, Keyword, Object
from keep.workflowmanager.dal.elasticsearch.models.client import es_client


class WorkflowExecutionDoc(Document):
    id = Keyword()
    workflow_id = Keyword()
    tenant_id = Keyword()
    workflow_revision = Integer()
    started = Date()
    triggered_by = Keyword()
    status = Keyword()
    is_running = Boolean()
    timeslot = Integer()
    execution_number = Integer()
    error = Text()
    execution_time = Integer()
    results = Object()
    is_test_run = Boolean()
    event_type = Keyword()
    event_id = Keyword()

    class Index:
        name = "workflow-engine-workflow-execution-docs"


# es_client.indices.delete(index=WorkflowExecutionDoc.Index.name, ignore_unavailable=True)
WorkflowExecutionDoc.init(using=es_client)
