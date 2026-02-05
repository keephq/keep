interface FloatOrIntSetting {
  max?: number;
  min?: number;
  type: "float" | "int";
  value: number;
}

interface BoolSetting {
  type: "bool";
  value: boolean;
}

interface BaseSetting {
  name: string;
  description: string;
}

export type AlgorithmSetting = BaseSetting & (FloatOrIntSetting | BoolSetting);

export interface Algorithm {
  name: string;
  description: string;
  last_time_reminded?: string;
}

export interface AIConfig {
  id: string;
  algorithm_id: string;
  tenant_id: string;
  settings: AlgorithmSetting[];
  settings_proposed_by_algorithm: AlgorithmSetting[];
  feedback_logs: string;
  algorithm: Algorithm;
}

export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  algorithm_configs: AIConfig[];
}

export interface AILogs {
  log: string;
}
