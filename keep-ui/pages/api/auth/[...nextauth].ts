import NextAuth, { NextAuthOptions } from 'next-auth';
import Auth0Provider from "next-auth/providers/auth0";

export const authOptions: NextAuthOptions = {
  providers: [
    Auth0Provider({
      clientId: process.env.AUTH0_CLIENT_ID!,
      clientSecret: process.env.AUTH0_CLIENT_SECRET!,
      issuer: process.env.AUTH0_ISSUER!
    })
  ],
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  // https://next-auth.js.org/configuration/callbacks#jwt-callback
  callbacks: {
    async jwt({ token, account, profile }) {
      // Keep the auth0 id_token so we will be able to query other
      // backend services
      console.log("JWT CALLBACK")
      if (account) {
        token.id_token = account.id_token
      }
      return token
    },
    async session({ session, token, user }) {
      // we keep the id_token in session so we can query other backend services
      // from the frontend.
      // see this - https://stackoverflow.com/questions/75431246/nextauth-v4-credentials-provider-adding-the-raw-token-to-the-session
      //@ts-ignore
      // TODO - fix this by adding id_token to the session interface
      console.log("SESSION CALLABACK");
      // @ts-ignore
      session.id_token = token.id_token;
      return session
    }

  }
};

export default NextAuth(authOptions);
