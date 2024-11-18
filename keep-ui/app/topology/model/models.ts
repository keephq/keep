import { InterfaceToType } from "@/utils/type-utils";
import type { Node } from "@xyflow/react";

export interface TopologyServiceDependency {
  serviceId: string;
  serviceName: string;
  protocol?: string;
}

export interface TopologyService {
  id: number;
  source_provider_id?: string;
  repository?: string;
  tags?: string[];
  service: string;
  display_name: string;
  description?: string;
  team?: string;
  email?: string;
  slack?: string;
  dependencies: TopologyServiceDependency[];
  ip_address?: string;
  mac_address?: string;
  manufacturer?: string;
  category?: string;
  application_ids: string[];
  // Added on client to optimize rendering
  applications: TopologyApplicationMinimal[];
}

// We need to convert interface to type because only types are allowed in @xyflow/react
// https://github.com/xyflow/web/issues/486
export type ServiceNodeType = Node<InterfaceToType<TopologyService>, string>;

export type TopologyNode = ServiceNodeType | Node;

export type TopologyServiceMinimal = {
  id: number;
  service: string;
  name: string;
};

export type TopologyApplicationMinimal = {
  id: string;
  name: string;
};

export type TopologyApplication = {
  id: string;
  name: string;
  description: string;
  services: TopologyServiceMinimal[];
  // TODO: Consider adding tags, cost of disruption, etc.
};
