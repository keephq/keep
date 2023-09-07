import os
import random
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select
from starlette_context import context, request_cycle_context

# This import is required to create the tables
from keep.api.core.config import config
from keep.api.core.db import engine
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.alert import *
from keep.api.models.db.provider import *
from keep.api.models.db.tenant import *
from keep.api.models.db.workflow import *
from keep.contextmanager.contextmanager import ContextManager


@pytest.fixture
def ctx_store() -> dict:
    """
    Create a context store
    """
    return {"X-Request-ID": random.randint(10000, 90000)}


@pytest.fixture(autouse=True)
def mocked_context(ctx_store) -> None:
    with request_cycle_context(ctx_store):
        yield context


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id=SINGLE_TENANT_UUID, workflow_id="1234")


@pytest.fixture
def db_session():
    # Set up an SQLite in-memory database and create tables
    mock_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(mock_engine)

    # Mock the environment variables so db.py will use it
    os.environ["DATABASE_CONNECTION_STRING"] = "sqlite:///:memory:"

    # Create a session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mock_engine)
    session = SessionLocal()

    # Prepopulate the database with test data
    workflow_data = [
        Workflow(
            id="test-id-1",
            name="test-name-1",
            tenant_id=SINGLE_TENANT_UUID,
            description="test workflow",
            created_by="test@keephq.dev",
            interval=0,
            workflow_raw="test workflow raw",
        ),
        Workflow(
            id="test-id-2",
            name="test-name-2",
            tenant_id=SINGLE_TENANT_UUID,
            description="test workflow",
            created_by="test@keephq.dev",
            interval=0,
            workflow_raw="test workflow raw",
        ),
        # Add more data as needed
    ]
    session.add_all(workflow_data)
    session.commit()

    with patch("keep.api.core.db.engine", mock_engine):
        yield

    # Clean up after the test
    session.close()
