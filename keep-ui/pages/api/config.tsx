import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({
    AUTH_TYPE: process.env.AUTH_TYPE,
    PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
    API_URL: process.env.API_URL
  });
}
