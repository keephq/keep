import NextAuth, { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import Auth0Provider from "next-auth/providers/auth0";
import { getApiURL } from "utils/apiUrl";
import { AuthenticationType } from "utils/authenticationType";

const authType = process.env.AUTH_TYPE as AuthenticationType;

export const multiTenantAuthOptions = {
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
    signIn: "/signin",
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
    },
    async authorize({  req, token  }) {
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
} as AuthOptions;

export const noAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'NoAuth',
      credentials: {},
      async authorize(credentials, req) {
        // Return a static user object with a predefined token
        console.log("MOCKING AUTHENTICATION");
        return {
          id: 'static-user',
          name: 'Static User',
          email: 'static@example.com',
          accessToken: '123', // Static token
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
} as AuthOptions;

console.log("authType: ", authType);
export default (authType == AuthenticationType.MULTI_TENANT)
  ? NextAuth(multiTenantAuthOptions)
  : (authType == AuthenticationType.SINGLE_TENANT)
  ? NextAuth(singleTenantAuthOptions)
  : NextAuth(noAuthOptions);
