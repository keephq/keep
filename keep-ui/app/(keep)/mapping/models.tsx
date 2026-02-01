export interface MappingRule {
  id: number;
  tenant_id: string;
  priority: number;
  name: string;
  description?: string;
  file_name?: string;
  created_by?: string;
  created_at: Date;
  updated_by?: string;
  last_updated_at: Date;
  disabled: boolean;
  override: boolean;
  type: "csv" | "topology";
  condition?: string;
  matchers: string[][];
  rows: { [key: string]: any }[];
  attributes?: string[];
  is_multi_level?: boolean;
  new_property_name?: string;
  prefix_to_remove?: string;
}
