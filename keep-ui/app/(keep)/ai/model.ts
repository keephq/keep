export interface AIConfig {
  algorithm_id: string;
  settings: any[];
  settings_proposed_by_algorithm: any;
  feedback_logs: string;
  algorithm: {
    name: string;
    description: string;
  };
}

export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  algorithm_configs: AIConfig[];
  is_mining_enabled: boolean;
  algorithm_verbose_name: string;
}

export interface AILogs {
  log: string;
}
