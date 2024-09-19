export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  is_mining_enabled: boolean;
  is_manual_mining_enabled: boolean;
  algorithm_verbose_name: string;
  mining_configuration: {
    sliding_window: number;
    min_alert_number: number;
  };
}

export interface AILogs {
  log: string;
}