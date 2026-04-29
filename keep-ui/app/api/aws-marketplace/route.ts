import { NextRequest } from "next/server";
import { redirect } from "next/navigation";

export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get("content-type") || "";
    let token: string | null = null;

    if (contentType.includes("application/x-www-form-urlencoded")) {
      const body = await request.formData();
      token = body.get("x-amzn-marketplace-token") as string | null;
    } else {
      const body = await request.json();
      token = body["x-amzn-marketplace-token"] ?? null;
    }

    if (!token) {
      return new Response("Bad Request: missing x-amzn-marketplace-token", { status: 400 });
    }

    const base64EncodedToken = encodeURIComponent(btoa(token));
    return redirect(`/signin?amt=${base64EncodedToken}`);
  } catch (error) {
    console.error("Error processing request:", error);
    return new Response("Bad Request", { status: 400 });
  }
}
