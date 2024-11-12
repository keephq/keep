export interface AIConfig {
  algorithm_id: string;
  settings: any;
  feedback_logs: string;
  algorithm: {
    name: string;
    description: string;
  }
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