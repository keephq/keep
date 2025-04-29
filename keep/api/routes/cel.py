import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
from celpy import CELParseError

router = APIRouter()
logger = logging.getLogger(__name__)


class CelExpressionPayload(BaseModel):
    cel: str


@router.post(
    "/validate",
    description="Validate CEL expression",
)
def validate(
    cel_payload: CelExpressionPayload,
) -> Any:
    try:
        CelToAstConverter.convert_to_ast(cel_payload.cel)
        return 200
    except CELParseError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e)},
        )
