import os
import random
from unittest.mock import Mock, patch

import mysql.connector
import pytest
from dotenv import find_dotenv, load_dotenv
from pytest_docker.plugin import get_docker_services
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine
from starlette_context import context, request_cycle_context

# This import is required to create the tables
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.elastic import ElasticClient
from keep.api.models.db.alert import *
from keep.api.models.db.provider import *
from keep.api.models.db.rule import *
from keep.api.models.db.tenant import *
from keep.api.models.db.user import *
from keep.api.models.db.workflow import *
from keep.contextmanager.contextmanager import ContextManager

load_dotenv(find_dotenv())


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
    os.environ["STORAGE_MANAGER_DIRECTORY"] = "/tmp/storage-manager"
    return ContextManager(tenant_id=SINGLE_TENANT_UUID, workflow_id="1234")


@pytest.fixture(scope="session")
def docker_services(
    docker_compose_command,
    docker_compose_file,
    docker_compose_project_name,
    docker_setup,
    docker_cleanup,
):
    """Start the MySQL service (or any other service from docker-compose.yml)."""

    # If we are running in Github Actions, we don't need to start the docker services
    # as they are already handled by the Github Actions
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in Github Actions, skipping docker services")
        yield
        return

    # For local development, you can avoid spinning up the mysql container every time:
    if os.getenv("SKIP_DOCKER"):
        yield
        return

    # Else, start the docker services
    try:
        import inspect

        stack = inspect.stack()
        # this is a hack to support more than one docker-compose file
        for frame in stack:
            # if its a db_session, then we need to use the mysql docker-compose file
            if frame.function == "db_session":
                docker_compose_file = docker_compose_file.replace(
                    "docker-compose.yml", "docker-compose-mysql.yml"
                )
                break
            # if its a elastic_client, then we need to use the elastic docker-compose file
            elif frame.function == "elastic_client":
                docker_compose_file = docker_compose_file.replace(
                    "docker-compose.yml", "docker-compose-elastic.yml"
                )
                break

        with get_docker_services(
            docker_compose_command,
            docker_compose_file,
            docker_compose_project_name,
            docker_setup,
            docker_cleanup,
        ) as docker_service:
            yield docker_service

    except Exception as e:
        print(f"Docker services could not be started: {e}")
        # Optionally, provide a fallback or mock service here
        yield None


def is_mysql_responsive(host, port, user, password, database):
    try:
        # Create a MySQL connection
        connection = mysql.connector.connect(
            host=host, port=port, user=user, password=password, database=database
        )

        # Check if the connection is established
        if connection.is_connected():
            return True

    except Exception:
        print("Mysql still not up")
        pass

    return False


@pytest.fixture(scope="session")
def mysql_container(docker_ip, docker_services):
    try:
        if os.getenv("SKIP_DOCKER") or os.getenv("GITHUB_ACTIONS") == "true":
            print("Running in Github Actions or SKIP_DOCKER is set, skipping mysql")
            yield
            return
        docker_services.wait_until_responsive(
            timeout=60.0,
            pause=0.1,
            check=lambda: is_mysql_responsive(
                "127.0.0.1", 3306, "root", "keep", "keep"
            ),
        )
        yield "mysql+pymysql://root:keep@localhost:3306/keep"
    except Exception:
        print("Exception occurred while waiting for MySQL to be responsive")
    finally:
        print("Tearing down MySQL")
        if docker_services:
            docker_services.down()


@pytest.fixture
def db_session(request):
    # Create a database connection
    if request and hasattr(request, "param") and "db" in request.param:
        db_type = request.param.get("db")
        db_connection_string = request.getfixturevalue(f"{db_type}_container")
        mock_engine = create_engine(db_connection_string)
    # sqlite
    else:
        db_connection_string = "sqlite:///:memory:"
        mock_engine = create_engine(
            db_connection_string,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    SQLModel.metadata.create_all(mock_engine)

    # Mock the environment variables so db.py will use it
    os.environ["DATABASE_CONNECTION_STRING"] = db_connection_string

    # Create a session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mock_engine)
    session = SessionLocal()
    # Prepopulate the database with test data

    # 1. Create a tenant
    tenant_data = [
        Tenant(id=SINGLE_TENANT_UUID, name="test-tenant", created_by="tests@keephq.dev")
    ]
    session.add_all(tenant_data)
    session.commit()
    # 2. Create some workflows
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
        WorkflowExecution(
            id="test-execution-id-1",
            workflow_id="mock_alert",
            tenant_id=SINGLE_TENANT_UUID,
            triggered_by="keep-test",
            status="success",
            execution_number=1,
            results={},
        ),
        WorkflowToAlertExecution(
            id=1,
            workflow_execution_id="test-execution-id-1",
            alert_fingerprint="mock_alert",
            event_id="mock_event_id",
        ),
        # Add more data as needed
    ]
    session.add_all(workflow_data)
    session.commit()

    with patch("keep.api.core.db.engine", mock_engine):
        yield session

    # delete the database
    SQLModel.metadata.drop_all(mock_engine)
    # Clean up after the test
    session.close()


@pytest.fixture
def mocked_context_manager():
    context_manager = Mock(spec=ContextManager)
    # Simulate contexts as needed for each test case
    context_manager.steps_context = {}
    context_manager.providers_context = {}
    context_manager.event_context = {}
    context_manager.click_context = {}
    context_manager.foreach_context = {"value": None}
    context_manager.dependencies = set()
    context_manager.get_full_context.return_value = {
        "steps": {},
        "providers": {},
        "event": {},
        "alert": {},
        "foreach": {"value": None},
        "env": {},
    }
    return context_manager


def is_elastic_responsive(host, port, user, password):
    try:
        elastic_client = ElasticClient(
            hosts=[f"http://{host}:{port}"],
            basic_auth=(user, password),
        )
        info = elastic_client.client.info()
        return True if info else False
    except Exception:
        print("Elastic still not up")
        pass

    return False


@pytest.fixture(scope="session")
def elastic_container(docker_ip, docker_services):
    try:
        if os.getenv("SKIP_DOCKER") or os.getenv("GITHUB_ACTIONS") == "true":
            print("Running in Github Actions or SKIP_DOCKER is set, skipping mysql")
            yield
            return
        docker_services.wait_until_responsive(
            timeout=60.0,
            pause=0.1,
            check=lambda: is_elastic_responsive(
                "127.0.0.1", 9200, "elastic", "keeptests"
            ),
        )
        yield True
    except Exception:
        print("Exception occurred while waiting for MySQL to be responsive")
    finally:
        print("Tearing down ElasticSearch")
        if docker_services:
            docker_services.down()


@pytest.fixture
def elastic_client(request):
    os.environ["ELASTIC_ENABLED"] = "true"
    os.environ["ELASTIC_USER"] = "elastic"
    os.environ["ELASTIC_PASSWORD"] = "keeptests"
    os.environ["ELASTIC_HOSTS"] = "http://localhost:9200"
    request.getfixturevalue("elastic_container")
    elastic_client = ElasticClient()
    yield elastic_client
