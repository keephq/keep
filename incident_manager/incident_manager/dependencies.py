from typing import Annotated

from llama_index.core import VectorStoreIndex
from fastapi import Request, Depends

def get_vector_db_index(request: Request) -> VectorStoreIndex:
    """Get the vector database index."""

    return request.app.state.vector_db_index

vector_db_index_dependency = Annotated[VectorStoreIndex, Depends(get_vector_db_index)]
