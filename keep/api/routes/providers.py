import click
from fastapi import APIRouter, Depends

from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser

router = APIRouter()


@router.get(
    "/",
    description="Get providers",
)
def get_providers(context: click.Context = Depends(click.get_current_context)):
    parser = Parser()
    parser.load_providers_config({}, context.params.get("providers_file"))
    context_manager = ContextManager.get_instance()
    return context_manager.providers_context
