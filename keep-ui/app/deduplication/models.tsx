export interface DeduplicationRule {
  id: string;
  name: string;
  description: string;
  default: boolean;
  distribution: { hour: number; number: number }[];
  provider_type: string;
  last_updated: string;
  last_updated_by: string;
  created_at: string;
  created_by: string;
  enabled: boolean;
  fingerprint_fields: string[];
  ingested: number;
  dedup_ratio: number;
}
