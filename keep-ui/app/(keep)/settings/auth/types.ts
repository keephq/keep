export interface ApiKey {
  reference_id: string;
  secret: string;
  created_by: string;
  created_at: string;
  last_used?: string;
  role?: string;
}
