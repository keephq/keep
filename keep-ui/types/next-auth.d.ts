import NextAuth from "next-auth";

declare module "next-auth" {
  /**
   * Returned by `useSession`, `getSession` and received as a prop on the `SessionProvider` React Context
   */
  interface Session {
    user: User;
    accessToken?: string;
    tenantId?: string;
  }
  interface User {
    name: string;
    email: string;
    accessToken: string;
    tenantId?: string;
  }
}
