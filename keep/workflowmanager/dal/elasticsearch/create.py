import os
from keep.api.core.elastic import create_elastic_client
from keep.workflowmanager.dal.elasticsearch.elasticsearchworkflowrepository import (
    ElasticSearchWorkflowRepository,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow import WorkflowDoc
from keep.workflowmanager.dal.elasticsearch.models.workflow_execution import (
    WorkflowExecutionDoc,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow_execution_log import (
    WorkflowExecutionLogDoc,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow_version import (
    WorkflowVersionDoc,
)


elastic_index_suffix = os.environ.get("ELASTIC_INDEX_SUFFIX", "workflow-engine")

config_dict = {}

def create_elasticsearch_workflow_repository():
    elastic_search_client = create_elastic_client()

    if not config_dict.get("are_models_intialized", False):
        WorkflowDoc.init(
            using=elastic_search_client,
        )
        WorkflowExecutionDoc.init(
            using=elastic_search_client,
        )
        WorkflowExecutionLogDoc.init(
            using=elastic_search_client,
        )
        WorkflowVersionDoc.init(
            using=elastic_search_client,
        )

        config_dict["are_models_intialized"] = True

    return ElasticSearchWorkflowRepository(elastic_search_client=elastic_search_client)
