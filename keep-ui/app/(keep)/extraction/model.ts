export interface ExtractionRule {
  id: number;
  priority: number;
  name: string;
  description?: string;
  created_by?: string;
  created_at: Date;
  updated_at?: Date;
  updated_by?: string;
  disabled: boolean;
  pre: boolean;
  condition?: string;
  attribute: string;
  regex: string;
}
