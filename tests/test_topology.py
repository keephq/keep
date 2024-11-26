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
from tests.fixtures.client import setup_api_key


VALID_API_KEY = "valid_api_key"


def create_service(db_session, tenant_id, id):
    service = TopologyService(
        tenant_id=tenant_id,
        service="test_service_" + id,
        display_name=id,
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

    application_dto.services.append(TopologyServiceDtoIn(id=123))
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
    assert result[0].services[0].service == "test_service_1"
    assert result[0].services[1].service == "test_service_2"


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

    application_data = {"name": "New Application", "services": [{"id": service.id}]}

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

    invalid_update_data = {"name": "Invalid Application", "services": [{"id": "123"}]}

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
