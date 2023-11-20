import NextAuth, { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import Auth0Provider from "next-auth/providers/auth0";
import { getApiURL } from "utils/apiUrl";
import { AuthenticationType } from "utils/authenticationType";

const authType = process.env.AUTH_TYPE as AuthenticationType;
/*

This file implements three different authentication flows:
1. Multi-tenant authentication using Auth0
2. Single-tenant authentication using username/password
3. No authentication

Depends on authType which can be NO_AUTH, SINGLE_TENANT or MULTI_TENANT
Note that the same environment variable should be set in the backend too.

*/


// multi tenant authentication using Auth0
const multiTenantAuthOptions = {
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
  pages: {
    signIn: '/signin',
  },
  callbacks: {
    async jwt({ token, account, profile, user }) {
      // https://next-auth.js.org/configuration/callbacks#jwt-callback
      if (account) {
        token.accessToken = account.id_token;
      }

      if ((profile as any)?.keep_tenant_id) {
        token.keep_tenant_id = (profile as any).keep_tenant_id;
      }

      return token;
    },
    async session({ session, token }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      session.tenantId = token.keep_tenant_id as string;
      return session;
     }
    }
  } as AuthOptions;

// Single tenant authentication using username/password
const singleTenantAuthOptions = {
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
          const accessToken = user.accessToken as string;
          const tenantId = user.tenantId as string;
          // Assuming the response contains the user's data if authentication was successful
          if (user && user.accessToken) {
            return {
              ...user,
              accessToken,
              tenantId,
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
        token.tenantId = user.tenantId;
      }
      return token;
    },
    async session({ session, token, user }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      session.tenantId = token.tenantId as string;
    return session;
    }
  },
} as AuthOptions;


// No authentication
const noAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'NoAuth',
      credentials: {},
      async authorize(credentials, req) {
        // Return a static user object with a predefined token
        return {
          id: 'keep-user-for-no-auth-purposes',
          name: 'Keep',
          email: 'keep@example.com',
          accessToken: 'keep-token-for-no-auth-purposes', // Static token for no-auth purposes - DO NOT USE IN PRODUCTION
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // If the user object exists, set the static token
      if (user) {
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      return session;
    },
  },
  pages: {
    signIn: '/signin',
  },
} as AuthOptions;

console.log("Starting Keep frontend with auth type: ", authType);
export const authOptions = (authType === AuthenticationType.MULTI_TENANT)
  ? multiTenantAuthOptions
  : (authType === AuthenticationType.SINGLE_TENANT)
    ? singleTenantAuthOptions
    : noAuthOptions;

export default NextAuth(authOptions);
