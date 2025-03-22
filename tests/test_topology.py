from datetime import datetime
import uuid
import pytest
from sqlmodel import select

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.topology import (
    TopologyApplication,
    TopologyApplicationDtoIn,
    TopologyService,
    TopologyServiceDependency,
    TopologyServiceDtoIn,
)
from keep.topologies.topologies_service import (
    TopologiesService,
    ApplicationNotFoundException,
    InvalidApplicationDataException,
    ServiceNotFoundException,
)
from tests.fixtures.client import setup_api_key, client, test_app  # noqa: F401


VALID_API_KEY = "valid_api_key"


def create_service(db_session, tenant_id, external_id):
    service = TopologyService(
        external_id=external_id,
        tenant_id=tenant_id,
        service="test_service_" + external_id,
        display_name=external_id,
        repository="test_repository",
        tags=["test_tag"],
        description="test_description",
        team="test_team",
        email="test_email",
        slack="test_slack",
        updated_at=datetime.now(),
    )
    db_session.add(service)
    db_session.commit()
    return service


def test_get_all_topology_data(db_session):
    service_1 = create_service(db_session, SINGLE_TENANT_UUID, "1")
    service_2 = create_service(db_session, SINGLE_TENANT_UUID, "2")

    result = TopologiesService.get_all_topology_data(SINGLE_TENANT_UUID, db_session)
    # We have no dependencies, so we should not return any services
    assert len(result) == 0

    dependency = TopologyServiceDependency(
        tenant_id=SINGLE_TENANT_UUID,
        service_id=service_1.id,
        depends_on_service_id=service_2.id,
        updated_at=datetime.now(),
    )
    db_session.add(dependency)
    db_session.commit()

    result = TopologiesService.get_all_topology_data(SINGLE_TENANT_UUID, db_session)
    assert len(result) == 1
    assert result[0].service == "test_service_1"

    result = TopologiesService.get_all_topology_data(
        SINGLE_TENANT_UUID, db_session, include_empty_deps=True
    )
    assert len(result) == 2
    assert result[0].service == "test_service_1"
    assert result[1].service == "test_service_2"


def test_get_applications_by_tenant_id(db_session):
    service_1 = create_service(db_session, SINGLE_TENANT_UUID, "1")
    service_2 = create_service(db_session, SINGLE_TENANT_UUID, "2")
    application_1 = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID,
        name="Test Application",
        services=[service_1, service_2],
    )
    application_2 = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID,
        name="Test Application 2",
        services=[service_1],
    )
    db_session.add(application_1)
    db_session.add(application_2)
    db_session.commit()

    result = TopologiesService.get_applications_by_tenant_id(
        SINGLE_TENANT_UUID, db_session
    )
    assert len(result) == 2
    assert result[0].name == "Test Application"
    assert len(result[0].services) == 2
    assert result[1].name == "Test Application 2"
    assert len(result[1].services) == 1

def test_create_application_by_tenant_id(db_session):
    application_dto = TopologyApplicationDtoIn(name="New Application", services=[])

    with pytest.raises(InvalidApplicationDataException):
        TopologiesService.create_application_by_tenant_id(
            SINGLE_TENANT_UUID, application_dto, db_session
        )

    application_dto.services.append(TopologyServiceDtoIn(id=uuid.uuid4()))
    with pytest.raises(ServiceNotFoundException):
        TopologiesService.create_application_by_tenant_id(
            SINGLE_TENANT_UUID, application_dto, db_session
        )

    application_dto.services = []

    service_1 = create_service(db_session, SINGLE_TENANT_UUID, "1")
    service_2 = create_service(db_session, SINGLE_TENANT_UUID, "2")

    application_dto.services.append(TopologyServiceDtoIn(id=service_1.id))
    application_dto.services.append(TopologyServiceDtoIn(id=service_2.id))

    result = TopologiesService.create_application_by_tenant_id(
        SINGLE_TENANT_UUID, application_dto, db_session
    )
    assert result.name == "New Application"

    result = TopologiesService.get_applications_by_tenant_id(
        SINGLE_TENANT_UUID, db_session
    )
    print(result)
    assert len(result) == 1
    assert result[0].name == "New Application"
    assert len(result[0].services) == 2

    services_names = [s.service for s in result[0].services]
    assert "test_service_1" in services_names
    assert "test_service_2" in services_names


def test_update_application_by_id(db_session):
    application = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID, name="Old Application"
    )
    db_session.add(application)
    db_session.commit()

    application_dto = TopologyApplicationDtoIn(name="Updated Application", services=[])

    random_uuid = uuid.uuid4()
    with pytest.raises(ApplicationNotFoundException):
        TopologiesService.update_application_by_id(
            SINGLE_TENANT_UUID, random_uuid, application_dto, db_session
        )

    result = TopologiesService.update_application_by_id(
        SINGLE_TENANT_UUID, application.id, application_dto, db_session
    )
    assert result.name == "Updated Application"


def test_delete_application_by_id(db_session):
    application = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID, name="Test Application"
    )
    db_session.add(application)
    db_session.commit()

    TopologiesService.delete_application_by_id(
        SINGLE_TENANT_UUID, application.id, db_session
    )
    result = db_session.exec(
        select(TopologyApplication).where(TopologyApplication.id == application.id)
    ).first()
    assert result is None


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_get_applications(db_session, client, test_app):
    setup_api_key(
        db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="webhook"
    )

    service_1 = create_service(db_session, SINGLE_TENANT_UUID, "1")
    service_2 = create_service(db_session, SINGLE_TENANT_UUID, "2")
    service_3 = create_service(db_session, SINGLE_TENANT_UUID, "3")

    application_1 = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID,
        name="Test Application",
        services=[service_1, service_2],
    )
    application_2 = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID,
        name="Test Application 2",
        services=[service_3],
    )
    db_session.add(application_1)
    db_session.add(application_2)
    db_session.commit()

    response = client.get(
        "/topology/applications", headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "Test Application"
    assert response.json()[1]["services"][0]["name"] == "3"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_create_application(db_session, client, test_app):
    setup_api_key(
        db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="webhook"
    )

    service = create_service(db_session, SINGLE_TENANT_UUID, "1")

    application_data = {"name": "New Application", "services": [{"id": str(service.id)}]}

    response = client.post(
        "/topology/applications",
        json=application_data,
        headers={"x-api-key": VALID_API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Application"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_update_application(db_session, client, test_app):
    setup_api_key(
        db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="webhook"
    )

    application = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID, name="Old Application"
    )
    db_session.add(application)
    db_session.commit()

    update_data = {
        "name": "Updated Application",
    }

    random_uuid = uuid.uuid4()
    response = client.put(
        f"/topology/applications/{random_uuid}",
        json=update_data,
        headers={"x-api-key": VALID_API_KEY},
    )
    assert response.status_code == 404

    response = client.put(
        f"/topology/applications/{application.id}",
        json=update_data,
        headers={"x-api-key": VALID_API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Application"

    invalid_update_data = {"name": "Invalid Application", "services": [{"id": str(random_uuid)}]}

    response = client.put(
        f"/topology/applications/{application.id}",
        json=invalid_update_data,
        headers={"x-api-key": VALID_API_KEY},
    )
    assert response.status_code == 400


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_delete_application(db_session, client, test_app):
    setup_api_key(
        db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="webhook"
    )
    random_uuid = uuid.uuid4()

    response = client.delete(
        f"/topology/applications/{random_uuid}", headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 404

    application = TopologyApplication(
        tenant_id=SINGLE_TENANT_UUID, name="Test Application"
    )
    db_session.add(application)
    db_session.commit()

    response = client.delete(
        f"/topology/applications/{application.id}", headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Application deleted successfully"


def test_clean_before_import(db_session):
    # Setup: Create services, applications, and dependencies for one tenant
    tenant_id = SINGLE_TENANT_UUID

    service_1 = create_service(db_session, tenant_id, "1")
    service_2 = create_service(db_session, tenant_id, "2")

    application = TopologyApplication(
        tenant_id=tenant_id,
        name="Test Application",
        services=[service_1, service_2],
    )
    db_session.add(application)
    db_session.commit()

    dependency = TopologyServiceDependency(
        service_id=service_1.id,
        depends_on_service_id=service_2.id,
        tenant_id=tenant_id,
        updated_at=datetime.now(),
    )
    db_session.add(dependency)
    db_session.commit()

    # Assert data exists before cleaning
    assert db_session.exec(select(TopologyService).where(TopologyService.tenant_id == tenant_id)).all()
    assert db_session.exec(select(TopologyApplication).where(TopologyApplication.tenant_id == tenant_id)).all()
    assert db_session.exec(select(TopologyServiceDependency).where(TopologyApplication.tenant_id == tenant_id)).all()

    # Act: Call the clean_before_import function
    TopologiesService.clean_before_import(tenant_id, db_session)

    # Assert: Ensure all data is deleted for this tenant
    assert not db_session.exec(select(TopologyService).where(TopologyService.tenant_id == tenant_id)).all()
    assert not db_session.exec(select(TopologyApplication).where(TopologyApplication.tenant_id == tenant_id)).all()
    assert not db_session.exec(select(TopologyServiceDependency).where(TopologyApplication.tenant_id == tenant_id)).all()


def test_import_to_db(db_session):
    # Setup: Define topology data to import
    tenant_id = SINGLE_TENANT_UUID

    # Do same operation twice - import and re-import
    for i in range(2):

        s1_id = str(uuid.uuid4())
        s2_id = str(uuid.uuid4())

        topology_data = {
            "services": [
                {
                    "id": s1_id,
                    "external_id": "1",
                    "service": "test_service_1",
                    "display_name": "Service 1",
                    "tags": ["tag1"],
                    "team": "team1",
                    "email": "test1@example.com",
                },
                {
                    "id": s2_id,
                    "external_id": "2",
                    "service": "test_service_2",
                    "display_name": "Service 2",
                    "tags": ["tag2"],
                    "team": "team2",
                    "email": "test2@example.com",
                },
            ],
            "applications": [
                {
                    "name": "Test Application 1",
                    "description": "Application 1 description",
                    "services": [s1_id],
                },
                {
                    "name": "Test Application 2",
                    "description": "Application 2 description",
                    "services": [s2_id],
                },
            ],
            "dependencies": [
                {
                    "service_id": s1_id,
                    "depends_on_service_id": s2_id,
                }
            ],
        }

        TopologiesService.import_to_db(topology_data, db_session, tenant_id)

        services = db_session.exec(select(TopologyService).where(TopologyService.tenant_id == tenant_id)).all()
        assert len(services) == 2
        assert services[0].service == "test_service_1"
        assert services[1].service == "test_service_2"

        applications = db_session.exec(select(TopologyApplication).where(TopologyApplication.tenant_id == tenant_id)).all()
        assert len(applications) == 2
        assert applications[0].name == "Test Application 1"
        assert applications[1].name == "Test Application 2"

        dependencies = db_session.exec(select(TopologyServiceDependency)).all()
        assert len(dependencies) == 1
        assert str(dependencies[0].service_id) == s1_id
        assert str(dependencies[0].depends_on_service_id) == s2_id
