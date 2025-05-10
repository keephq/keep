import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
from celpy import CELParseError

router = APIRouter()
logger = logging.getLogger(__name__)


class CelExpressionPayload(BaseModel):
    cel: str


class CelExpressionValidationMarker(BaseModel):
    columnStart: int
    columnEnd: int


@router.post(
    "/validate",
    description="Validate CEL expression",
)
def validate(
    cel_payload: CelExpressionPayload,
) -> Any:
    try:
        CelToAstConverter.convert_to_ast(cel_payload.cel)
        return []
    except CELParseError as e:
        return [
            CelExpressionValidationMarker(
                columnStart=e.column,
                columnEnd=e.column + 1,
            )
        ]
