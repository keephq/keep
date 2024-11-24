import { NextResponse, type NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";
import type { JWT } from "next-auth/jwt";
import { getApiURL } from "@/utils/apiUrl";

export async function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // Keep it on header so it can be used in server components
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-url", request.url);

  // Get the token using next-auth/jwt with the correct type
  const token = (await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  })) as JWT | null;

  // Handle legacy /backend/ redirects
  if (pathname.startsWith("/backend/")) {
    const apiUrl = getApiURL();
    const newURL = pathname.replace("/backend/", apiUrl + "/");
    const queryString = searchParams.toString();
    const urlWithQuery = queryString ? `${newURL}?${queryString}` : newURL;

    console.log(`Redirecting ${pathname} to ${urlWithQuery}`);
    return NextResponse.rewrite(urlWithQuery);
  }

  // Allow API routes to pass through
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // If not authenticated and not on signin page, redirect to signin
  if (!token && !pathname.startsWith("/signin")) {
    console.log("Redirecting to signin page because user is not authenticated");
    return NextResponse.redirect(new URL("/signin", request.url));
  }

  // If authenticated and on signin page, redirect to dashboard
  if (token && pathname.startsWith("/signin")) {
    console.log(
      "Redirecting to incidents because user try to get /signin but already authenticated"
    );
    return NextResponse.redirect(new URL("/incidents", request.url));
  }

  // Role-based routing (NOC users)
  if (token?.role === "noc" && !pathname.startsWith("/alerts")) {
    return NextResponse.redirect(new URL("/alerts/feed", request.url));
  }

  // Allow all other authenticated requests
  console.log("Allowing request to pass through");
  console.log("Request URL: ", request.url);

  return NextResponse.next({
    request: {
      // Apply new request headers
      headers: requestHeaders,
    },
  });
}

// Update the matcher to handle static files and public routes
export const config = {
  matcher: [
    "/((?!keep_big\\.svg$|gnip\\.webp|api/aws-marketplace$|monitoring|_next/static|_next/image|favicon\\.ico).*)",
  ],
};
