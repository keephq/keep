import { TProviderLabels } from "../providers";

export const PROVIDER_LABELS: Record<TProviderLabels, string> = {
  alert: 'Alert',
  messaging: 'Messaging',
  ticketing: 'Ticketing',
  data: 'Data',
  queue: 'Queue',
}

export const PROVIDER_LABELS_KEYS = Object.keys(PROVIDER_LABELS);