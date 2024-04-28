import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";
import { getApiURL } from "utils/apiUrl";

export default withAuth(function middleware(req) {
  const { pathname, searchParams } = new URL(req.url);
  // Redirect /backend/ to the API
  if (pathname.startsWith("/backend/")) {
    let apiUrl = getApiURL();
    const newURL = pathname.replace("/backend/", apiUrl + "/");

    // Convert searchParams back into a query string
    const queryString = searchParams.toString();
    const urlWithQuery = queryString ? `${newURL}?${queryString}` : newURL;

    console.log(`Redirecting ${pathname} to ${urlWithQuery}`);
    return NextResponse.rewrite(urlWithQuery);
  }

  // api routes are ok too
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // If the user's role is 'noc' and they are not on the '/alerts' page, redirect them
  // todo: should be more robust, but this is a quick solution
  //       I guess first step should be some mapping ~ {role: [allowed_pages]}
  //       and the second step would be to get it dymnamically from an API
  //       or some role-based routing
  if (req.nextauth.token?.role === "noc" && !pathname.startsWith("/alerts")){
    return NextResponse.redirect(new URL("/alerts/feed", req.url));
  }

  // Continue with the normal flow for other cases
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!keep_big\\.svg$|gnip\\.webp|signin$|api\/aws\-marketplace$).*)"], // Adjust as needed
};
