export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  algorithms: {
    name: string;
    description: string;
    settings: any;
    feedback_log: string;
  }[];
}

export interface AILogs {
  log: string;
}