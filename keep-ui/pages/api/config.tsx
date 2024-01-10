import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  res.status(200).json({
    AUTH_TYPE: process.env.AUTH_TYPE,
    PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
    PUSHER_HOST: process.env.PUSHER_HOST,
    PUSHER_PORT: parseInt(process.env.PUSHER_PORT || "6001"),
    API_URL: process.env.API_URL,
  });
}
