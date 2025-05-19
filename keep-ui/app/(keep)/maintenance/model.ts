export interface MaintenanceRule {
  id: number;
  name: string;
  description?: string;
  created_by: string;
  cel_query: string;
  start_time: Date;
  end_time?: Date;
  duration_seconds?: number;
  updated_at?: Date;
  suppress: boolean;
  enabled: boolean;
  ignore_statuses: string[];
}

export interface MaintenanceRuleCreate {
  name: string;
  description?: string;
  cel_query: string;
  start_time: Date;
  end_time?: Date;
  duration_seconds?: number;
  enabled: boolean;
  ignore_statuses: string[];
}
