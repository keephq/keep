export interface DeduplicationRule {
  id: string;
  name: string;
  description: string;
  default: boolean;
  distribution: { hour: number; number: number }[];
  provider_type: string;
  provider_id: string;
  last_updated: string;
  last_updated_by: string;
  created_at: string;
  created_by: string;
  enabled: boolean;
  fingerprint_fields: string[];
  ingested: number;
  dedup_ratio: number;
  // full_deduplication is true if the deduplication rule is a full deduplication rule
  full_deduplication: boolean;
  ignore_fields: string[];
  is_provisioned: boolean;
}
