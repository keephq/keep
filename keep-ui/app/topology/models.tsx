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
}
