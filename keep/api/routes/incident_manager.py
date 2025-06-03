import logging
from uuid import UUID

from fastapi import APIRouter

import httpx
from pydantic import BaseModel

from keep.api.core.config import config


class RelatedIncidentDto(BaseModel):
    id: UUID
    user_generated_name: str
    user_summary: str


class RelatedIncidentsDto(BaseModel):
    limit: int
    offset: int
    count: int
    items: list[RelatedIncidentDto]  # Assuming items are incident IDs

router = APIRouter()
logger = logging.getLogger(__name__)


INCIDENT_MANAGER_URL = str(config("INCIDENT_MANAGER_URL", cast=str))

@router.get("/retrieve-related-incidents")
async def retrieve_related_incidents(
    incident_id: str,
    top_k: int = 10,
) -> RelatedIncidentsDto:
    """
    Retrieve related incidents based on the provided incident ID.
    
    Args:
        incident_id (str): The ID of the incident to find related incidents for.
        top_k (int): The number of related incidents to return.
    
    Returns:
        list[str]: A list of related incident IDs.
    """
    print(f"{INCIDENT_MANAGER_URL=}")
    # Placeholder for actual retrieval logic
    logger.info(f"Retrieving related incidents for incident ID: {incident_id}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{INCIDENT_MANAGER_URL}/retrieve-related-incidents",
            params={"incident_id": incident_id, "top_k": top_k}
        )
        if response.status_code != 200:
            logger.error(f"Failed to retrieve related incidents: {response.text}")
            return RelatedIncidentsDto(
                limit=0,
                offset=0,
                count=0,
                items=[]
            )
        print(f"Response: {response.json()}")
        data = response.json()
        return RelatedIncidentsDto(
            limit=0,
            offset=0,
            count=len(data),
            items=[
                RelatedIncidentDto(
                    id=UUID(item["id"]),
                    user_generated_name=item["user_generated_name"],
                    user_summary=item["user_summary"]
                ) for item in data
            ]
        )

    
