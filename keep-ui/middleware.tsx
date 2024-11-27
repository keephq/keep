import { NextResponse, type NextRequest } from "next/server";
// TODO: is it safe to remove these imports?
import { getToken } from "next-auth/jwt";
import type { JWT } from "next-auth/jwt";
import { getApiURL } from "@/utils/apiUrl";
import { config as authConfig } from "@/auth.config";
import NextAuth from "next-auth";

const { auth } = NextAuth(authConfig);

// Helper function to detect mobile devices
function isMobileDevice(userAgent: string): boolean {
  return /Mobile|Android|iP(hone|od)|IEMobile|BlackBerry|Kindle|Silk-Accelerated|(hpw|web)OS|Opera M(obi|ini)/.test(
    userAgent
  );
}

export async function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // Check if request is from mobile device
  const userAgent = request.headers.get("user-agent") || "";
  if (isMobileDevice(userAgent)) {
    return NextResponse.redirect(new URL("/mobile", request.url));
  }

  const session = await auth();
  const role = session?.userRole;
  const isAuthenticated = !!session;
  // Keep it on header so it can be used in server components
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-url", request.url);
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
  if (!isAuthenticated && !pathname.startsWith("/signin")) {
    console.log("Redirecting to signin page because user is not authenticated");
    return NextResponse.redirect(new URL("/signin", request.url));
  }

  // If authenticated and on signin page, redirect to incidents
  if (isAuthenticated && pathname.startsWith("/signin")) {
    console.log(
      "Redirecting to incidents because user try to get /signin but already authenticated"
    );
    return NextResponse.redirect(new URL("/incidents", request.url));
  }

  // Role-based routing (NOC users)
  if (role === "noc" && !pathname.startsWith("/alerts")) {
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
