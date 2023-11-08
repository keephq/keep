import { withAuth } from "next-auth/middleware";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";
const useAuthentication = process.env.NEXT_PUBLIC_USE_AUTHENTICATION == "true";

export default isSingleTenant && !useAuthentication
  ? () => {}
  : withAuth({
      callbacks: {
        authorized: async ({ req, token }) => {
          const pathname = req.nextUrl.pathname;
          if (pathname.endsWith("svg")) {
            return true;
          }

          if (
            token &&
            (token.exp as number) >= Math.floor(new Date().getTime() / 1000)
          ) {
            return true;
          }

          return false;
        },
      },
      pages: {
        signIn: "/signin",
      },
    });
