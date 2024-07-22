export interface AIStats {
  alerts_count: number;
  incidents_count: number;
  first_alert_datetime?: Date;
  is_mining_enabled: boolean;
}
