import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { getApiURL } from "@/utils/apiUrl";

// Use auth as a wrapper for middleware logic
export default auth(async (req) => {
  const { pathname, searchParams } = req.nextUrl;

  // Keep it on header so it can be used in server components
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set("x-url", req.url);

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
  if (!req.auth && !pathname.startsWith("/signin")) {
    console.log("Redirecting to signin page because user is not authenticated");
    return NextResponse.redirect(new URL("/signin", req.url));
  }

  // else if authenticated and on signin page, redirect to dashboard
  if (req.auth && pathname.startsWith("/signin")) {
    console.log(
      "Redirecting to incidents because user try to get /signin but already authenticated"
    );
    return NextResponse.redirect(new URL("/incidents", req.url));
  }

  // Role-based routing (NOC users)
  if (req.auth?.user?.role === "noc" && !pathname.startsWith("/alerts")) {
    return NextResponse.redirect(new URL("/alerts/feed", req.url));
  }

  // Allow all other authenticated requests
  console.log("Allowing request to pass through");
  console.log("Request URL: ", req.url);
  // console.log("Request headers: ", requestHeaders)
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
    "/((?!keep_big\\.svg$|gnip\\.webp|api/aws-marketplace$|monitoring|_next/static|_next/image|favicon\\.ico).*)",
  ],
};
