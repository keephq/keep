export interface Service {
  id: string;
  soruce_provider_id?: string;
  repository?: string;
  tags?: string[];
  service: string;
  display_name: string;
  description?: string;
  team?: string;
  application?: string;
  email?: string;
  slack?: string;
}

// ServiceDependency interface to define the structure of service dependencies
export interface ServiceDependency {
  serviceId: string;
  protocol?: string;
}
