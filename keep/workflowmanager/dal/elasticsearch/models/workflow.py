from elasticsearch.dsl import Document, Text, Date, Boolean, Integer, Keyword


class WorkflowDoc(Document):
    id = Keyword()
    tenant_id = Keyword()
    name = Text()
    description = Text()
    created_by = Text()
    updated_by = Text()
    creation_time = Date()
    interval = Integer()
    workflow_raw = Text()
    is_deleted = Boolean()
    is_disabled = Boolean()
    revision = Integer()
    last_updated = Date()
    provisioned = Boolean()
    provisioned_file = Text()
    is_test = Boolean()

    class Index:
        name = "workflow-engine-workflow-docs"
