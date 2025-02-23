export interface IncidentMetrics {
  total_incidents: number;
  resolved_incidents: number;
  deleted_incidents: number;
  unresolved_incidents: number;
}

export interface IncidentDurations {
  shortest_duration_seconds: number;
  shortest_duration_incident_id: string;
  longest_duration_seconds: number;
  longest_duration_incident_id: string;
}

export interface SeverityMetrics {
  critical: string;
  high: string;
}

// Base Incident model
export interface Incident {
  incident_name?: string;
  incident_id?: string;
}

// Reoccurring Incident extends Incident
export interface ReoccurringIncident extends Incident {
  occurrence_count?: number;
}

export interface IncidentData {
  incident_metrics: IncidentMetrics;
  top_services_affected: string[];
  common_incident_names: string[];
  severity_metrics: SeverityMetrics;
  incident_durations: IncidentDurations;
  mean_time_to_detect_seconds: number;
  mean_time_to_resolve_seconds: number;
  most_occuring_incidents: string[];
  most_incident_reasons: Record<string, string[]>;
  recurring_incidents: ReoccurringIncident[];
}
