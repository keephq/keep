import { NextResponse } from "next/server";
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

export const middleware = auth(async (request) => {
  const { pathname, searchParams } = request.nextUrl;

  // go to temporary placeholder for mobile devices
  const userAgent = request.headers.get("user-agent") || "";
  if (
    isMobileDevice(userAgent) &&
    !pathname.startsWith("/mobile") &&
    process.env.KEEP_READ_ONLY === "true"
  ) {
    return NextResponse.redirect(new URL("/mobile", request.url));
  }

  const session = await auth();
  const role = session?.userRole;
  const isAuthenticated = !!request.auth;
  // Keep it on header so it can be used in server components
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-url", request.url);
  // Handle legacy /backend/ redirects (when API_URL is not set and frontend act as a proxy)
  if (pathname.startsWith("/backend/")) {
    const apiUrl = getApiURL();
    const newURL = pathname.replace("/backend/", apiUrl + "/");
    const queryString = searchParams.toString();
    const urlWithQuery = queryString ? `${newURL}?${queryString}` : newURL;

    console.log(`Redirecting ${pathname} to ${urlWithQuery}`);
    return NextResponse.rewrite(urlWithQuery);
  }

  // Allow mobile route to pass through
  if (pathname.startsWith("/mobile")) {
    return NextResponse.next();
  }

  // If not authenticated and not on signin page, redirect to signin
  if (
    !isAuthenticated &&
    !pathname.startsWith("/signin") &&
    !pathname.startsWith("/health") &&
    !pathname.startsWith("/error")
  ) {
    const redirectTo = request.nextUrl.href || "/incidents";
    console.log(
      `Redirecting ${pathname} to signin page because user is not authenticated`
    );
    return NextResponse.redirect(
      new URL(`/signin?callbackUrl=${redirectTo}`, request.url)
    );
  }

  // If authenticated and on signin page, redirect to incidents
  if (isAuthenticated && pathname.startsWith("/signin")) {
    const redirectTo =
      request.nextUrl.searchParams.get("callbackUrl") || "/incidents";
    console.log(
      `Redirecting to ${redirectTo} because user try to get /signin but already authenticated`
    );
    return NextResponse.redirect(new URL(redirectTo, request.url));
  }

  // Role-based routing (NOC users)
  if (role === "noc" && !pathname.startsWith("/alerts")) {
    return NextResponse.redirect(new URL("/alerts/feed", request.url));
  }

  // Allow all other authenticated requests
  console.log("Allowing request to pass through", request.url);
  console.log("Request URL: ", request.url);

  return NextResponse.next({
    request: {
      // Apply new request headers
      headers: requestHeaders,
    },
  });
});

// Update the matcher to handle static files and public routes
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - keep_big.svg (logo)
     * - keep.svg (logo)
     * - gnip.webp (logo)
     * - api/aws-marketplace (aws marketplace)
     * - api/auth (auth)
     * - monitoring (monitoring)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - icons (providers' logos)
     */
    "/((?!keep_big\\.svg$|gnip\\.webp|api/aws-marketplace$|api/auth|monitoring|_next/static|_next/image|favicon\\.ico|icons|keep\\.svg).*)",
  ],
};
