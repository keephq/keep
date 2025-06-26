from elasticsearch.dsl import Document, Text, Date, Boolean, Integer, Keyword


class WorkflowVersionDoc(Document):
    id = Keyword()
    workflow_id = Keyword()
    tenant_id = Keyword()
    revision = Integer()
    workflow_raw = Text()
    updated_by = Text()
    updated_at = Date()
    is_valid = Boolean()
    is_current = Boolean()
    comment = Text()

    class Index:
        name = "workflow-engine-workflow-version-docs"
