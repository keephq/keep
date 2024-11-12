import type { NextApiRequest, NextApiResponse } from "next";

const error = (req: NextApiRequest, res: NextApiResponse) => {
  throw new Error("API throw error test");
  res.status(200).json({ name: "John Doe" });
};

export default error;
