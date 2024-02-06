export interface InternalConfig {
  AUTH_TYPE: string;
  PUSHER_DISABLED: boolean;
  PUSHER_HOST?: string;
  PUSHER_PORT?: number;
  PUSHER_APP_KEY: string;
  PUSHER_CLUSTER?: string;
  POSTHOG_KEY: string;
  POSTHOG_HOST: string;
  POSTHOG_DISABLED: string;
}
