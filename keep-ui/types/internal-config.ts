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
  // Keep Docs
  KEEP_DOCS_URL: string;
  // Keep Contact Us
  KEEP_CONTACT_US_URL: string;
  // Hide sensitive fields
  KEEP_HIDE_SENSITIVE_FIELDS: boolean;
  // Show debug info in workflow builder UI
  KEEP_WORKFLOW_DEBUG: boolean;
  HIDE_NAVBAR_DEDUPLICATION: boolean;
  HIDE_NAVBAR_WORKFLOWS: boolean;
  HIDE_NAVBAR_SERVICE_TOPOLOGY: boolean;
  HIDE_NAVBAR_MAPPING: boolean;
  HIDE_NAVBAR_EXTRACTION: boolean;
  HIDE_NAVBAR_MAINTENANCE_WINDOW: boolean;
  HIDE_NAVBAR_AI_PLUGINS: boolean;
}
