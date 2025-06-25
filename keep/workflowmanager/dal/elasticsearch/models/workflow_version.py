from elasticsearch.dsl import Document, Text, Date, Boolean, Integer, Keyword
from keep.workflowmanager.dal.elasticsearch.models.client import es_client


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


# es_client.indices.delete(index=WorkflowVersionDoc.Index.name, ignore_unavailable=True)
WorkflowVersionDoc.init(using=es_client)
