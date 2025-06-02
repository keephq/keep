import logging

from fastapi import Depends, APIRouter
from incident_manager.schemas import IncidentBulkPostBody, IncidentDto
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
)
from llama_index.core.schema import QueryBundle
from llama_index.core.schema import Document

from incident_manager.dependencies import vector_db_index_dependency

logger = logging.getLogger(__name__)
incident_router = APIRouter()


@incident_router.post("/index-incident")
async def create_incident(
    incidents: IncidentBulkPostBody, vector_db_index: vector_db_index_dependency
) -> None:
    documents = [
        Document(
            text=incident.user_generated_name,
            metadata={
                "incident_id": incident.id,
                "user_summary": incident.user_summary,
            },
        )
        for incident in incidents.incidents
    ]
    await vector_db_index.ainsert_nodes(
        documents,
    )


@incident_router.get("/retrieve-related-incidents")
async def retrieve_related_incidents(
    incident_id: str,
    vector_db_index: vector_db_index_dependency,
    top_k: int = 10,
) -> list[IncidentDto]:
    nodes = vector_db_index.vector_store.get_nodes(
        filters=MetadataFilters(
            filters=[
                MetadataFilter(
                    key="incident_id",
                    value=incident_id,
                    op=FilterOperator.EQ,
                )
            ]
        )
    )
    if not nodes:
        logger.warning(f"No incidents found with ID: {incident_id}")
        return []
    incident_embedding = nodes[0].embedding
    related_nodes = vector_db_index.as_retriever(
        similarity_top_k=top_k,
    )
    related_nodes = await related_nodes.aretrieve(
        str_or_query_bundle=QueryBundle(
            query_str="",
            embedding=incident_embedding,
        )
    )
    return [
        IncidentDto(
            id=node.metadata["incident_id"],
            user_generated_name=node.text,
            user_summary=node.metadata["user_summary"],
        )
        for node in related_nodes
    ]
