import { NextRequest, NextResponse } from "next/server";
import NextAuthMiddleware from "next-auth/middleware";
import { getApiURL } from "utils/apiUrl";

export const config = {
  matcher: [
    '/((?!keep_big\\.svg$|signin$).*)',
  ],
};

export function middleware(req: NextRequest) {
  const { pathname } = new URL(req.url);

  // Redirect /backend/ to the API
  if (pathname.startsWith('/backend/')) {
    let apiUrl = getApiURL();
    const newURL = pathname.replace('/backend/', apiUrl + '/');
    console.log(`Redirecting ${pathname} to ${newURL}`);
    return NextResponse.rewrite(newURL);
  }

  // NextAuth middleware with custom authorized callback
  return NextAuthMiddleware(req, {
    callbacks: {
      authorized: async ({ token }) => {
        // Check if the user's role is 'noc' and redirect to /alerts
        if (token?.role === 'noc' && pathname !== '/alerts') {
          return NextResponse.redirect(new URL('/alerts', req.url));
        }
        return !!token; // Continue only if token exists (user is authenticated)
      },
    },
  });
}
