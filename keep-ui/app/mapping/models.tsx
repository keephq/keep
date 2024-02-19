export interface MappingRule {
  id?: number;
  tenant_id: string;
  priority: number;
  created_by?: string;
  created_at: Date;
  disabled: boolean;
  override: boolean;
  condition?: string;
  matchers: string[];
  rows: { [key: string]: any }[];
}
