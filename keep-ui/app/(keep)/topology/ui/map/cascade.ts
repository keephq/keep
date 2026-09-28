import { TopologyService } from "@/app/(keep)/topology/model";
// import enums directly from types.ts: going through the model index pulls a
// large dependency graph that is circular under jest's CJS transform
import { Severity, Status } from "@/entities/alerts/model/types";
import type { AlertDto } from "@/entities/alerts/model/types";

const DOWN_SEVERITIES: Severity[] = [
  Severity.Critical,
  Severity.Error,
  Severity.High,
];

/**
 * A service is considered "down" when it has at least one firing alert with
 * a down-level severity (critical / error / high — the node border is red).
 */
function isDown(alerts: AlertDto[]): boolean {
  return alerts.some(
    (alert) =>
      alert.status === Status.Firing && DOWN_SEVERITIES.includes(alert.severity as Severity)
  );
}

/**
 * Cascade warning computation, ported from dephealth-ui (cascade.js).
 *
 * For every "down" service, walk upstream through critical edges and mark
 * every affected service with the number of distinct down services it is
 * affected by. Down services themselves are not marked (they are the cause,
 * not the victim).
 *
 * Criticality is approximated at node level (keep has no per-edge
 * criticality in its topology model): an edge is critical when the target
 * service is tagged `critical` (i.e. it is a critical dependency for at
 * least one reporter).
 *
 * Cycle-safe: the upstream BFS tracks visited nodes, so cyclic dependency
 * graphs terminate (a direct A <-> B cycle just stops the walk).
 */
export function computeCascadeWarnings(
  topologyData: TopologyService[],
  alertsByService: Map<string, AlertDto[]>
): Map<string, number> {
  const downServices = new Set<string>();
  for (const service of topologyData) {
    if (isDown(alertsByService.get(service.service) ?? [])) {
      downServices.add(service.service);
    }
  }
  if (downServices.size === 0) {
    return new Map();
  }

  // Reverse adjacency: dependency -> services that depend on it.
  // An edge is critical when the target service is tagged `critical`.
  const criticalServices = new Set(
    topologyData
      .filter((service) => (service.tags ?? []).includes("critical"))
      .map((service) => service.service)
  );
  const upstream = new Map<string, string[]>();
  for (const service of topologyData) {
    for (const dependency of service.dependencies) {
      if (!criticalServices.has(dependency.serviceName)) {
        continue;
      }
      const sources = upstream.get(dependency.serviceName) ?? [];
      sources.push(service.service);
      upstream.set(dependency.serviceName, sources);
    }
  }

  const cascadeCount = new Map<string, Set<string>>();
  for (const down of downServices) {
    const visited = new Set<string>([down]);
    const queue = [down];
    while (queue.length > 0) {
      const current = queue.shift()!;
      for (const source of upstream.get(current) ?? []) {
        if (visited.has(source)) {
          continue; // cycle protection
        }
        visited.add(source);
        if (downServices.has(source)) {
          continue; // down services are their own root cause
        }
        const sources = cascadeCount.get(source) ?? new Set<string>();
        sources.add(down);
        cascadeCount.set(source, sources);
        queue.push(source);
      }
    }
  }

  return new Map(
    Array.from(cascadeCount.entries()).map(([name, sources]) => [
      name,
      sources.size,
    ])
  );
}
