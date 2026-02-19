import json

from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.tasks.process_topology_task import process_topology

if __name__ == "__main__":
    services = {}
    environment = "production"
    with open("/tmp/service_definitions.json", "r") as file:
        service_definitions = json.load(file)
    with open("/tmp/service_dependencies.json", "r") as file:
        service_dependencies = json.load(file)
    for service_definition in service_definitions["data"]:
        name = service_definition["attributes"]["schema"].get("dd-service")
        services[name] = TopologyServiceInDto(
            source_provider_id="datadog",
            repository=service_definition["attributes"]["schema"]["integrations"].get(
                "github"
            ),
            tags=service_definition["attributes"]["schema"].get("tags"),
            service=name,
            display_name=name,
            environment=environment,
        )
    for service_dep in service_dependencies:
        service = services.get(service_dep)
        if not service:
            service = TopologyServiceInDto(
                source_provider_id="datadog",
                service=service_dep,
                display_name=service_dep,
                environment=environment,
            )
        dependencies = service_dependencies[service_dep].get("calls", [])
        service.dependencies = {dependency: "unknown" for dependency in dependencies}
        services[service_dep] = service
    topology_data = list(services.values())
    print(topology_data)

    process_topology("keep", topology_data, "datadog", "datadog")
