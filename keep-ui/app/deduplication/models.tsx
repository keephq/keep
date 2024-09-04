export interface DeduplicationRule {
  id: string;
  name: string;
  description: string;
  default: boolean;
  distribution: Record<string, any>;
  provider_type: string;
  last_updated: string;
  last_updated_by: string;
  created_at: string;
  created_by: string;
  enabled: boolean;
  default_fingerprint_fields: string[];
}
