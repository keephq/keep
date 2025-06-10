// TODO: move to entities/alerts/models

interface Option {
  label: string;
  value: string;
}

interface Tag {
  id?: string;
  name: string;
}

export interface ColumnConfiguration {
  column_visibility: Record<string, boolean>;
  column_order: string[];
  column_rename_mapping: Record<string, string>;
  column_time_formats: Record<string, string>;
  column_list_formats: Record<string, string>;
}

export interface Preset {
  id: string;
  name: string;
  options: Option[];
  is_private: boolean;
  is_noisy: boolean;
  counter_shows_firing_only: boolean;
  should_do_noise_now: boolean;
  alerts_count: number;
  created_by?: string;
  tags: Tag[];
  group_column?: string;
}

type TagPayload = {
  id?: string;
  name: string;
};

export type PresetCreateUpdateDto = {
  name: string;
  CEL: string;
  isPrivate: boolean;
  isNoisy: boolean;
  counterShowsFiringOnly: boolean;
  tags: TagPayload[];
};
