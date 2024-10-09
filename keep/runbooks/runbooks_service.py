import logging
from typing import List
from pydantic import ValidationError
from sqlalchemy.orm import  selectinload

from sqlmodel import Session, select
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
                relative_path=runbook_dto["file_path"],
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
    def get_all_runbooks(session: Session, tenant_id: str) -> List[RunbookDtoOut]:
        runbooks = session.exec(
            select(Runbook)
            .where(Runbook.tenant_id == tenant_id)
            .options(selectinload(Runbook.contents)).limit(1000)
        )

        return [RunbookDtoOut.from_orm(runbook) for runbook in runbooks]            