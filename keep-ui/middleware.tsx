import { NextRequest, NextResponse } from "next/server";
import NextAuthMiddleware from "next-auth/middleware";
import type { NextRequestWithAuth } from "next-auth/middleware";

export const config = {
  matcher: [
    '/((?!keep_big\\.svg$|signin$).*)',
  ],
};

export function middleware(req: NextRequest) {
  const { pathname } = new URL(req.url);

  if (pathname.startsWith('/backend/')) {
    const newURL = pathname.replace('/backend/', process.env.API_URL + '/');
    return NextResponse.rewrite(newURL);
  }

  // Use type assertion here
  return NextAuthMiddleware(req as unknown as NextRequestWithAuth);
}
