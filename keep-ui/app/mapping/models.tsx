export interface MappingRule {
  id: number;
  tenant_id: string;
  priority: number;
  name: string;
  description?: string;
  file_name?: string;
  created_by?: string;
  created_at: Date;
  disabled: boolean;
  override: boolean;
  condition?: string;
  matchers: string[];
  rows: { [key: string]: any }[];
  attributes?: string[];
  updated_by?:string;
  updated_at?:Date;
}
