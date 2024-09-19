import { InterfaceToType } from "utils/type-utils";
import type { Node } from "@xyflow/react";

export interface TopologyServiceDependency {
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
  application?: string;
  email?: string;
  slack?: string;
  dependencies: TopologyServiceDependency[];
  ip_address?: string;
  mac_address?: string;
  manufacturer?: string;
  applicationObject?: Application;
}

// We need to convert interface to type because only types are allowed in @xyflow/react
// https://github.com/xyflow/web/issues/486
export type ServiceNodeType = Node<InterfaceToType<TopologyService>, string>;

export type Application = {
  id: string;
  name: string;
  description: string;
  services: {
    id: string;
    name: string;
  }[];
  // TODO: Consider adding tags, cost of disruption, etc.
};
