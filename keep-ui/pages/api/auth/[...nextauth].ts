import NextAuth, { NextAuthOptions } from "next-auth";
import Auth0Provider from "next-auth/providers/auth0";

export const authOptions: NextAuthOptions = {
  providers: [
    Auth0Provider({
      clientId: process.env.AUTH0_CLIENT_ID!,
      clientSecret: process.env.AUTH0_CLIENT_SECRET!,
      issuer: process.env.AUTH0_ISSUER!,
    }),
  ],
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, account }) {
      // https://next-auth.js.org/configuration/callbacks#jwt-callback
      if (account) {
        token.accessToken = account.id_token;
      }
      return token;
    },
    async session({ session, token }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      return session;
    },
  },
};

export default NextAuth(authOptions);
