// TODO: move to entities/alerts/models

interface Option {
  readonly label: string;
  readonly value: string;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Preset {
  id: string;
  name: string;
  options: Option[];
  is_private: boolean;
  is_noisy: boolean;
  should_do_noise_now: boolean;
  alerts_count: number;
  created_by?: string;
  tags: Tag[];
}

export type PresetCreateUpdateDto = {
  name: string;
  CEL: string;
  isPrivate: boolean;
  isNoisy: boolean;
  tags: Tag[];
};
