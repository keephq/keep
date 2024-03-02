import os
import random
from unittest.mock import patch

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
def docker_compose_file(pytestconfig):
    docker_compose_keep_file = os.path.join(os.getcwd(), "docker-compose.yml")
    return docker_compose_keep_file


@pytest.fixture(scope="session")
def docker_setup(pytestconfig):
    docker_setup = "--env-file .env.tests up -d"
    return docker_setup


@pytest.fixture(scope="session")
def docker_compose_project_name(pytestconfig):
    project_name = "keep-e2e-tests"
    return project_name


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
    if os.getenv("SKIP_DOCKER") == "true":
        yield
        return

    os.environ["AUTH_TYPE"] = "SINGLE_TENANT"
    # Else, start the docker services
    try:
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


def is_port_responsive(host, port):
    import socket

    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Try to open the port
        s.connect((host, port))

        # Close the socket
        s.close()

        return True
    except Exception:
        pass

    return


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
        yield
    except Exception:
        print("Exception occurred while waiting for MySQL to be responsive")
    finally:
        print("Tearing down MySQL")
        if docker_services:
            docker_services.down()


@pytest.fixture
def db_session(request, mysql_container):
    # Few tests require a mysql database (mainly rules)
    if request and hasattr(request, "param") and request.param == "mysql":
        db_connection_string = "mysql+pymysql://root:keep@localhost:3306/keep"
        mock_engine = create_engine(db_connection_string)
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


@pytest.fixture(scope="session")
def keep_service(docker_services):
    """
    Start the `keep` service using its specific Docker Compose file.
    """
    try:
        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=lambda: is_port_responsive("localhost", 8080)
        )
        print("`keep` service is up and running.")
    except Exception as e:
        print(
            f"Exception occurred while waiting for `keep` service to be responsive: {e}"
        )

    yield docker_services
