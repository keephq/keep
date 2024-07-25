export interface Service {
  id: string;
  last_modified_time?: Date;
  soruce_provider_id?: string;
  source_control_url?: string;
  tags?: string[];
  service: string;
  display_name: string;
  description?: string;
  team?: string;
  application?: string;
  code?: string;
  email?: string;
  slack?: string;
}

// ServiceDependency interface to define the structure of service dependencies
export interface ServiceDependency {
  service: string;
  protocol: string;
}
