import type { NextApiRequest, NextApiResponse } from "next";
import {
  AuthenticationType,
  MULTI_TENANT,
  SINGLE_TENANT,
  NO_AUTH,
} from "utils/authenticationType";
import { getApiURL } from "utils/apiUrl";
import { get } from "http";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  let authType = process.env.AUTH_TYPE;

  // Backward compatibility
  if (authType === MULTI_TENANT) {
    authType = AuthenticationType.AUTH0;
  } else if (authType === SINGLE_TENANT) {
    authType = AuthenticationType.DB;
  } else if (authType === NO_AUTH) {
    authType = AuthenticationType.NOAUTH;
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
  res.status(200).json({
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
  });
}
