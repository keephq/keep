import { getApiURL } from "@/utils/apiUrl";
import {
  AuthType,
  MULTI_TENANT,
  NO_AUTH,
  SINGLE_TENANT,
} from "@/utils/authenticationType";

export function getConfig() {
  let authType = process.env.AUTH_TYPE;
  // Backward compatibility
  if (authType === MULTI_TENANT) {
    authType = AuthType.AUTH0;
  } else if (authType === SINGLE_TENANT) {
    authType = AuthType.DB;
  } else if (authType === NO_AUTH) {
    authType = AuthType.NOAUTH;
  } else if (Object.values(AuthType).includes(authType as AuthType)) {
    // Keep the auth type if it's a valid enum value
    authType = authType as AuthType;
  } else {
    // Default to NOAUTH
    authType = AuthType.NOAUTH;
  }

  // we want to support preview branches on vercel
  let API_URL_CLIENT;
  // if we are on vercel, default to getApiURL() if no API_URL_CLIENT is set
  if (process.env.VERCEL_GIT_COMMIT_REF) {
    API_URL_CLIENT = process.env.API_URL_CLIENT || getApiURL();
    // else, no default since we will use relative URLs
  } else {
    API_URL_CLIENT = process.env.API_URL_CLIENT;
  }
  return {
    AUTH_TYPE: authType,
    PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
    // could be relative (for ingress) or absolute (e.g. Pusher)
    PUSHER_HOST: process.env.PUSHER_HOST,
    PUSHER_PORT: process.env.PUSHER_HOST
      ? parseInt(process.env.PUSHER_PORT!)
      : undefined,
    PUSHER_APP_KEY: process.env.PUSHER_APP_KEY,
    PUSHER_CLUSTER: process.env.PUSHER_CLUSTER,
    // The API URL is used by the server to make requests to the API
    //   note that we need two different URLs for the client and the server
    //   because in some environments, e.g. docker-compose, the server can get keep-backend
    //   whereas the client (browser) can get only localhost
    API_URL: process.env.API_URL,
    // could be relative (e.g. for ingress) or absolute (e.g. for cloud run)
    API_URL_CLIENT: API_URL_CLIENT,
    POSTHOG_KEY: process.env.POSTHOG_KEY,
    POSTHOG_DISABLED: process.env.POSTHOG_DISABLED,
    POSTHOG_HOST: process.env.POSTHOG_HOST,
    SENTRY_DISABLED: process.env.SENTRY_DISABLED,
    READ_ONLY: process.env.KEEP_READ_ONLY === "true",
    OPEN_AI_API_KEY_SET: !!process.env.OPEN_AI_API_KEY || !!process.env.OPENAI_API_KEY,
    // NOISY ALERTS DISABLED BY DEFAULT TO SPARE SPACE ON THE TABLE
    NOISY_ALERTS_ENABLED: process.env.NOISY_ALERTS_ENABLED === "true",
  };
}
