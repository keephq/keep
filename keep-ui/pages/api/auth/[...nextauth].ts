import NextAuth from "next-auth";
import Auth0Provider from "next-auth/providers/auth0";
import { cookies } from 'next/headers';

const isSingleTenant = process.env.AUTH_ENABLED == "false";

console.log(isSingleTenant ? "Single tenant mode" : "Multi tenant mode");

export default isSingleTenant
  ? null
  : NextAuth({
      providers: [
        Auth0Provider({
          clientId: process.env.AUTH0_CLIENT_ID!,
          clientSecret: process.env.AUTH0_CLIENT_SECRET!,
          issuer: process.env.AUTH0_ISSUER!,
          authorization: `https://${process.env.AUTH0_DOMAIN}/authorize?response_type=code&prompt=login`,
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
    });
