export { default } from "next-auth/middleware";

// matchers - https://nextjs.org/docs/pages/building-your-application/routing/middleware#matcher

// exclude keep_big.svg from being protected
export const config = {
  matcher: [
    // Match all request paths except the specific path '/keep_big.svg'
    '/((?!keep_big\\.svg$|signin$).*)',
  ],
};
