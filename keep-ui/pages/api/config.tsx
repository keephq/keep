import { getConfig } from "@/utils/server/getConfig";
import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const config = getConfig();
  res.status(200).json(config);
}
