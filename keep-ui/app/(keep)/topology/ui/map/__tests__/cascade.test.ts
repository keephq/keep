import { computeCascadeWarnings } from "../cascade";
import type { TopologyService } from "@/app/(keep)/topology/model";
import { Severity, Status } from "@/entities/alerts/model/types";
import type { AlertDto } from "@/entities/alerts/model/types";

function service(
  name: string,
  dependencies: string[],
  tags: string[] = []
): TopologyService {
  return {
    id: name,
    service: name,
    display_name: name,
    tags,
    dependencies: dependencies.map((dependency, index) => ({
      id: `${name}-${index}`,
      serviceId: dependency,
      serviceName: dependency,
      protocol: "http",
    })),
    application_ids: [],
    applications: [],
    is_manual: false,
  } as TopologyService;
}

function firingAlert(service: string, severity: Severity): AlertDto {
  return {
    id: `${service}-${severity}`,
    event_id: `${service}-${severity}`,
    name: "DependencyDown",
    status: Status.Firing,
    severity,
    service,
    lastReceived: new Date(),
    environment: "unknown",
  } as AlertDto;
}

function alertsMap(
  alerts: AlertDto[]
): Map<string, AlertDto[]> {
  const map = new Map<string, AlertDto[]>();
  for (const alert of alerts) {
    const list = map.get(alert.service!) ?? [];
    list.push(alert);
    map.set(alert.service!, list);
  }
  return map;
}

describe("computeCascadeWarnings", () => {
  it("returns empty map when no service is down", () => {
    const topology = [
      service("a", ["b"], ["critical"]),
      service("b", []),
    ];
    const alerts = alertsMap([firingAlert("a", Severity.Warning)]);
    expect(computeCascadeWarnings(topology, alerts).size).toBe(0);
  });

  it("marks upstream services through critical dependencies", () => {
    // a depends on critical b (b is tagged), c depends on critical a (a is tagged):
    // b down -> a and c affected
    const topology = [
      service("a", ["b"], ["critical"]),
      service("b", [], ["critical"]),
      service("c", ["a"]),
    ];
    const alerts = alertsMap([firingAlert("b", Severity.Critical)]);
    const result = computeCascadeWarnings(topology, alerts);
    expect(result.get("a")).toBe(1);
    expect(result.get("c")).toBe(1);
    expect(result.has("b")).toBe(false); // the down service itself is not marked
  });

  it("does not propagate through non-critical dependencies", () => {
    // a depends on b, but b is not tagged critical
    const topology = [service("a", ["b"]), service("b", [])];
    const alerts = alertsMap([firingAlert("b", Severity.Critical)]);
    expect(computeWarningsSize(topology, alerts)).toBe(0);
  });

  it("counts distinct down sources", () => {
    // c depends critically on both a and b; a and b are down
    const topology = [
      service("c", ["a", "b"]),
      service("a", [], ["critical"]),
      service("b", [], ["critical"]),
    ];
    const alerts = alertsMap([
      firingAlert("a", Severity.Critical),
      firingAlert("b", Severity.High),
    ]);
    const result = computeCascadeWarnings(topology, alerts);
    expect(result.get("c")).toBe(2);
  });

  it("terminates on cyclic dependencies", () => {
    // a <-> b direct cycle through critical edges, c depends on a;
    // b is down: a is affected via the cycle, c is affected through a
    const topology = [
      service("a", ["b"], ["critical"]),
      service("b", ["a"], ["critical"]),
      service("c", ["a"], ["critical"]),
    ];
    const alerts = alertsMap([firingAlert("b", Severity.Critical)]);
    const result = computeCascadeWarnings(topology, alerts);
    expect(result.get("a")).toBe(1);
    expect(result.get("c")).toBe(1);
    expect(result.has("b")).toBe(false);
  });

  it("ignores resolved alerts", () => {
    const topology = [service("a", ["b"], ["critical"]), service("b", [])];
    const resolved = {
      ...firingAlert("b", Severity.Critical),
      status: Status.Resolved,
    };
    const result = computeCascadeWarnings(topology, alertsMap([resolved]));
    expect(result.size).toBe(0);
  });
});

function computeWarningsSize(
  topology: TopologyService[],
  alerts: Map<string, AlertDto[]>
): number {
  return computeCascadeWarnings(topology, alerts).size;
}
