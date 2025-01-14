


from keep.api.models.facet import CreateFacetDto, FacetDto
from uuid import UUID, uuid4

# from pydantic import BaseModel
from sqlmodel import Session

from keep.api.core.db import engine
from keep.api.models.db.facet import Facet, FacetType


def create_facet(tenant_id: str, facet: CreateFacetDto) -> FacetDto:
    with Session(engine) as session:
        facet_db = Facet(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=facet.name,
            description=facet.description,
            entity_type="incident",
            property_path=facet.property_path,
            type=FacetType.str.value,
            user_id="system"

        )
        session.add(facet_db)
        session.commit()
        return FacetDto(
            id=str(facet_db.id),
            property_path=facet_db.property_path,
            name=facet_db.name,
            description=facet_db.description,
            is_static=False,
            is_lazy=True,
            type=facet_db.type
        )
    return None


def delete_facet(tenant_id: str, facet_id: str) -> bool:
    with Session(engine) as session:
        facet = (
            session.query(Facet)
            .filter(Facet.tenant_id == tenant_id)
            .filter(Facet.id == UUID(facet_id))
            .first()
        )
        if facet:
            session.delete(facet)
            session.commit()
            return True
        return False


def get_facets(tenant_id: str, entity_type: str, facet_ids_to_load: list[str] = None) -> list[FacetDto]:
    with Session(engine) as session:
        query = session.query(
            Facet
        ).filter(Facet.tenant_id == tenant_id).filter(Facet.entity_type == entity_type)

        if facet_ids_to_load:
            query = query.filter(Facet.id.in_([UUID(id) for id in facet_ids_to_load]))

        facets_from_db: list[Facet] = query.all()

        facet_dtos = []

        for facet in facets_from_db:
            facet_dtos.append(
                FacetDto(
                    id=str(facet.id),
                    property_path=facet.property_path,
                    name=facet.name,
                    is_static=False,
                    is_lazy=True,
                    type=FacetType.str
                )
            )

        return facet_dtos
