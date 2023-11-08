import NextAuth, { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import Auth0Provider from "next-auth/providers/auth0";
import { getApiURL } from "utils/apiUrl";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";
const useAuthentication = process.env.NEXT_PUBLIC_USE_AUTHENTICATION == "true";

console.log(process.env.AUTH0_DOMAIN);

export const authOptions = {
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
} as AuthOptions;

// for single tenant, we will user username/password authentication
export const singleTenantAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "keep" },
        password: { label: "Password", type: "password", placeholder: "keep" },
      },
      async authorize(credentials, req) {
        const apiUrl = getApiURL();
        try {
          const response = await fetch(`${apiUrl}/signin`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(credentials),
          });

          if (!response.ok) {
            throw new Error("Failed to authenticate user");
          }

          const user = await response.json();
          const accessToken = user.accessToken;
          // Assuming the response contains the user's data if authentication was successful
          if (user && user.accessToken) {
            return {
              ...user,
              accessToken,
            };
          } else {
            return null;
          }
        } catch (error) {
          if (error instanceof Error) {
            console.error("Authentication error:", error.message);
          } else {
            console.error("Unknown authentication error:", error);
          }
        }
      },
    }),
  ],
  theme: {
    colorScheme: "auto", // "auto" | "dark" | "light"
    brandColor: "#000000", // Hex color code
    logo: "/keep_big.svg", // Absolute URL to image
    buttonText: "#000000", // Hex color code
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, user }) {
      // https://next-auth.js.org/configuration/callbacks#jwt-callback
      if (user) {
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token, user }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      return session;
    },
  },
} as AuthOptions;

export default isSingleTenant && !useAuthentication
  ? null
  : isSingleTenant
  ? NextAuth(singleTenantAuthOptions)
  : NextAuth(authOptions);
