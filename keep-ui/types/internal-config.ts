export interface InternalConfig {
  AUTH_TYPE: string;
  // Pusher
  PUSHER_DISABLED: boolean;
  PUSHER_HOST: string | undefined;
  PUSHER_PORT: number | undefined;
  PUSHER_APP_KEY: string | undefined;
  PUSHER_CLUSTER: string | undefined;
  // Posthog
  POSTHOG_KEY: string | undefined;
  POSTHOG_HOST: string | undefined;
  POSTHOG_DISABLED: string | undefined;
  // the API URL is used by the server to make requests to the API
  API_URL: string | undefined;
  // the API URL for the client (browser)
  // optional, defaults to /backend (relative)
  API_URL_CLIENT: string | undefined;
  // Sentry
  SENTRY_DISABLED: string | undefined;
  // READ ONLY
  READ_ONLY: boolean;
  OPEN_AI_API_KEY_SET: boolean;

  // NOISY ALERTS ENABLED
  NOISY_ALERTS_ENABLED: boolean;

  FRIGADE_DISABLED: string | undefined;
}
