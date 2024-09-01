import type { NextApiRequest, NextApiResponse } from "next";
import { AuthenticationType, MULTI_TENANT, SINGLE_TENANT, NO_AUTH } from "utils/authenticationType";

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

  res.status(200).json({
    AUTH_TYPE: authType,
    PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
    PUSHER_HOST: process.env.PUSHER_HOST,
    PUSHER_PORT: process.env.PUSHER_HOST
      ? parseInt(process.env.PUSHER_PORT!)
      : undefined,
    PUSHER_APP_KEY: process.env.PUSHER_APP_KEY,
    PUSHER_CLUSTER: process.env.PUSHER_CLUSTER,
    API_URL: process.env.API_URL,
    POSTHOG_KEY: process.env.POSTHOG_KEY,
    POSTHOG_DISABLED: process.env.POSTHOG_DISABLED,
    POSTHOG_HOST: process.env.POSTHOG_HOST,
  });
}
