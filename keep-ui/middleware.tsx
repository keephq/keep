import { withAuth } from "next-auth/middleware";


export default withAuth({
    callbacks: {
      authorized: async ({ req, token }) => {
        const pathname = req.nextUrl.pathname;
        if (pathname.endsWith("svg")) {
          return true;
        }
        // validate that token exists and is not expired
        // todo: understand how token shuold be validated in frontend (if it should)
        // todo 2: refresh token?
        if (token && (token.exp as number) > new Date().getTime() / 1000) {
          return true;
        }

        return false;
      },
    },
    pages: {
      signIn: "/signin",
    },
  });
