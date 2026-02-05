export interface EnrichmentEventLog {
  timestamp: string;
  message: string;
  context?: Record<string, any>;
}

export interface EnrichmentEventWithLogs {
  enrichment_event: EnrichmentEvent;
  logs: EnrichmentEventLog[];
}

export interface EnrichmentEvent {
  id: string;
  rule_id: number;
  alert_id: string;
  status: string;
  timestamp: string;
  execution_time?: number;
  enriched_fields?: Record<string, any>;
  tenant_id: string;
}

export interface PaginatedEnrichmentExecutionDto {
  limit: number;
  offset: number;
  count: number;
  items: EnrichmentEvent[];
}
