import logging
from pydantic import ValidationError
from sqlalchemy.orm import  selectinload

from sqlmodel import Session
from keep.api.models.db.runbook import (
    Runbook,
    RunbookContent,
    RunbookDtoOut
)
logger = logging.getLogger(__name__)


class RunbookService:
    @staticmethod
    def create_runbook(session: Session, tenant_id: str, runbook_dto: dict):
        try:
            new_runbook = Runbook(
                tenant_id=tenant_id,
                title=runbook_dto["title"],
                repo_id=runbook_dto["repo_id"],
                relative_path=runbook_dto["relative_path"],
                provider_type=runbook_dto["provider_type"],
                provider_id=runbook_dto["provider_id"]
            )

            session.add(new_runbook)
            session.flush()
            contents = runbook_dto["contents"] if runbook_dto["contents"] else []

            new_contents = [
                RunbookContent(
                    runbook_id=new_runbook.id,
                    content=content["content"],
                    link=content["link"],
                    encoding=content["encoding"],
                    file_name=content["file_name"]
                )
                for content in contents
            ]

            session.add_all(new_contents)
            session.commit()
            session.expire(new_runbook, ["contents"])
            session.refresh(new_runbook)  # Refresh the runbook instance
            result = RunbookDtoOut.from_orm(new_runbook)
            return result
        except ValidationError as e:
            logger.exception(f"Failed to create runbook {e}")

    @staticmethod
    def get_all_runbooks(session: Session, tenant_id: str, limit=25, offset=0) -> dict:
        query = session.query(Runbook).filter(
            Runbook.tenant_id == tenant_id,
        )

        total_count = query.count()  # Get the total count of runbooks matching the tenant_id
        runbooks = query.options(selectinload(Runbook.contents)).limit(limit).offset(offset).all()  # Fetch the paginated runbooks
        result = [RunbookDtoOut.from_orm(runbook) for runbook in runbooks]  # Convert runbooks to DTOs

        # Return total count and list of runbooks
        return {"total_count": total_count, "runbooks": result}    