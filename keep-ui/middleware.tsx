export { default } from "next-auth/middleware";

// matchers - https://nextjs.org/docs/pages/building-your-application/routing/middleware#matcher

// exclude keep_big.svg from being protected
export const config = {
  matcher: [
    // Exclude two pages from the middleware:
    // 1. Signin page (so that users can sign in)
    // 2. keep svg (so that it can be displayed on the signin page)
    '/((?!keep_big\\.svg$|signin$).*)',
  ],
};
