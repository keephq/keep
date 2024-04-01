import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === "POST") {
    const {
      "x-amzn-marketplace-token": token,
      "x-amzn-marketplace-offer-type": offerType,
    } = req.body;

    const base64EncodedToken = encodeURIComponent(btoa(token));

    // Redirect to the sign-in page or wherever you want
    // amt is amazon-marketplace-token
    res.writeHead(302, { Location: `/signin?amt=${base64EncodedToken}` });
    res.end();
  } else {
    // Handle any non-POST requests
    res.status(405).send("Method Not Allowed");
  }
}
