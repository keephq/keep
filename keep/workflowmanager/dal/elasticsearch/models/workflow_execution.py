from elasticsearch.dsl import Document, Text, Date, Boolean, Integer, Keyword, Object

class WorkflowExecutionDoc(Document):
    id = Keyword()
    workflow_id = Keyword()
    tenant_id = Keyword()
    workflow_revision = Integer()
    started = Date()
    triggered_by = Keyword()
    status = Keyword()
    is_running = Integer()
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
