export interface InternalConfig {
  AUTH_TYPE: string;
  PUSHER_DISABLED: boolean;
  PUSHER_HOST?: string;
  PUSHER_PORT?: number;
  PUSHER_APP_KEY: string;
  PUSHER_CLUSTER?: string;
  PUSHER_INGRESS: boolean; // e.g. for kubernetes/helmchart where the websocket endpoint is through the ingress
  POSTHOG_KEY: string;
  POSTHOG_HOST: string;
  POSTHOG_DISABLED: string;
  // the API URL is used by the server to make requests to the API
  API_URL: string;
  // the API URL for the client (browser)
  // optional, defaults to /backend (relative)
  API_URL_CLIENT?: string;
  // Sentry
  SENTRY_DISABLED: string;
  // READ ONLY
  READ_ONLY: boolean;
}
