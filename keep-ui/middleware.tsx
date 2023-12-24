import { NextRequest, NextResponse } from "next/server";
import NextAuthMiddleware from "next-auth/middleware";
import type { NextRequestWithAuth } from "next-auth/middleware";
import { getApiURL } from "utils/apiUrl";

export const config = {
  matcher: [
    '/((?!keep_big\\.svg$|signin$).*)',
  ],
};

export function middleware(req: NextRequest) {
  const { pathname } = new URL(req.url);

  if (pathname.startsWith('/backend/')) {
    let apiUrl = getApiURL();
    const newURL = pathname.replace('/backend/', apiUrl + '/');
    console.log(`Redirecting ${pathname} to ${newURL}`);
    return NextResponse.rewrite(newURL);
  }

  // Use type assertion here
  return NextAuthMiddleware(req as unknown as NextRequestWithAuth);
}
