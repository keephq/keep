import { NextRequest } from "next/server";
import { redirect } from "next/navigation";

export async function POST(request: NextRequest) {
  try {
    // In App Router, we need to parse the request body manually
    const body = await request.json();

    const token = body["x-amzn-marketplace-token"];
    const offerType = body["x-amzn-marketplace-offer-type"];

    // Base64 encode the token
    const base64EncodedToken = encodeURIComponent(btoa(token));

    // In App Router, we use the redirect function for redirects
    return redirect(`/signin?amt=${base64EncodedToken}`);
  } catch (error) {
    console.error("Error processing request:", error);
    return new Response("Bad Request", { status: 400 });
  }
}
