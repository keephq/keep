from contextlib import asynccontextmanager
import sys
import asyncio
import logging

from fastapi import FastAPI
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.milvus import MilvusVectorStore

from incident_manager.api import incident_router
from incident_manager.settings import config_settings

logging.basicConfig(
    level=config_settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def wait_for_vector_db(delay=3) -> MilvusVectorStore:
    """Try to connect to VectorDB, retrying if necessary."""
    while True:
        try:
            vector_store = MilvusVectorStore(
                collection_name="incident_collection",
                dim=config_settings.EMBEDDING_DIMENSION,
            )
            logger.info("Successfully connected to VectorDB.")
            return vector_store
        except Exception as e:
            logger.warning(f"VectorDB connection attempt failed: {e}")
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event for FastAPI app.

    This function is called when the app starts and stops.
    """
    # Retry until MySQL is ready
    vector_store = await wait_for_vector_db()
    logger.info("VectorDB is ready. Proceeding with app startup.")
    
    vector_db_index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store
    )
    app.state.vector_db_index = vector_db_index
    yield

    await vector_store.aclient.close()
    vector_store.client.close()


def create_app():
    """Create FastAPI app with lifespan and routes."""
    app = FastAPI(
        lifespan=lifespan,
        title="Incident Manager",
    )

    # Include routes
    app.include_router(incident_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config_settings.INCIDENT_MANAGER_PORT,
        reload=config_settings.DEBUG,
    )
