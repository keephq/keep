export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  algorithm_configs: {
    settings: any;
    feedback_log: string;
    algorithm: {
      name: string;
      description: string;
    }
  }[];
}

export interface AILogs {
  log: string;
}