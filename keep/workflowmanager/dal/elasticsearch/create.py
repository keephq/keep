import os
from keep.api.core.elastic import create_elastic_client
from keep.workflowmanager.dal.elasticsearch.elasticsearchworkflowrepository import (
    ElasticSearchWorkflowRepository,
)

elastic_index_suffix = os.environ.get("ELASTIC_INDEX_SUFFIX", "workflow-engine")


def create_elasticsearch_workflow_repository():
    elastic_search_client = create_elastic_client()
    return ElasticSearchWorkflowRepository(
        elastic_search_client=elastic_search_client, index_suffix=elastic_index_suffix
    )
