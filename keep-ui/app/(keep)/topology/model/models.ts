import { InterfaceToType } from "@/utils/type-utils";
import type { Node } from "@xyflow/react";
import { KeyedMutator } from "swr";

export interface TopologyServiceDependency {
  id: string;
  serviceId: string;
  serviceName: string;
  protocol?: string;
}

export interface TopologyService {
  id: string;
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
  incidents?: number;
  is_manual: boolean;
}

export interface TopologyServiceWithMutator extends TopologyService {
  topologyMutator: KeyedMutator<TopologyService[]>;
}

// We need to convert interface to type because only types are allowed in @xyflow/react
// https://github.com/xyflow/web/issues/486
export type ServiceNodeType = Node<InterfaceToType<TopologyServiceWithMutator>, string>;

export type TopologyNode = ServiceNodeType | Node;

export type TopologyServiceMinimal = {
  id: string;
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
  repository: string;
  services: TopologyServiceMinimal[];
  // TODO: Consider adding tags, cost of disruption, etc.
};
