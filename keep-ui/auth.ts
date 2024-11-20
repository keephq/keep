import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Keycloak from "next-auth/providers/keycloak";
import Auth0 from "next-auth/providers/auth0";
import MicrosoftEntraID from "@auth/core/providers/microsoft-entra-id";
import { AuthError } from "next-auth";
import { AuthenticationError, AuthErrorCodes } from "@/errors";

export class BackendRefusedError extends AuthError {
  static type = "BackendRefusedError";
}

import { getApiURL } from "@/utils/apiUrl";
import {
  AuthenticationType,
  NoAuthUserEmail,
  NoAuthTenant,
  MULTI_TENANT,
  SINGLE_TENANT,
  NO_AUTH,
} from "@/utils/authenticationType";
import type { User } from "next-auth";

// Determine auth type with backward compatibility
const authTypeEnv = process.env.AUTH_TYPE;
const authType =
  authTypeEnv === MULTI_TENANT
    ? AuthenticationType.AUTH0
    : authTypeEnv === SINGLE_TENANT
    ? AuthenticationType.DB
    : authTypeEnv === NO_AUTH
    ? AuthenticationType.NOAUTH
    : (authTypeEnv as AuthenticationType);

async function refreshAccessToken(token: any) {
  const issuerUrl = process.env.KEYCLOAK_ISSUER;
  const refreshTokenUrl = `${issuerUrl}/protocol/openid-connect/token`;

  try {
    const response = await fetch(refreshTokenUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        client_id: process.env.KEYCLOAK_ID!,
        client_secret: process.env.KEYCLOAK_SECRET!,
        grant_type: "refresh_token",
        refresh_token: token.refreshToken,
      }),
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      throw new Error(
        `Refresh token failed: ${response.status} ${response.statusText}`
      );
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken,
    };
  } catch (error) {
    console.error("Error refreshing access token:", error);
    return {
      ...token,
      error: "RefreshAccessTokenError",
    };
  }
}

// Define provider configurations
const providerConfigs = {
  [AuthenticationType.AUTH0]: [
    Auth0({
      clientId: process.env.AUTH0_CLIENT_ID!,
      clientSecret: process.env.AUTH0_CLIENT_SECRET!,
      issuer: process.env.AUTH0_ISSUER!,
      authorization: {
        params: {
          prompt: "login",
        },
      },
    }),
  ],
  [AuthenticationType.DB]: [
    Credentials({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "keep" },
        password: { label: "Password", type: "password", placeholder: "keep" },
      },
      async authorize(credentials): Promise<User | null> {
        try {
          const response = await fetch(`${getApiURL()}/signin`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error("Authentication failed:", errorData);
            throw new AuthenticationError(AuthErrorCodes.INVALID_CREDENTIALS);
          }

          const user = await response.json();
          if (!user.accessToken) return null;

          return {
            id: user.id,
            name: user.name,
            email: user.email,
            accessToken: user.accessToken,
            tenantId: user.tenantId,
            role: user.role,
          };
        } catch (error) {
          if (error instanceof TypeError && error.message === "fetch failed") {
            throw new AuthenticationError(AuthErrorCodes.CONNECTION_REFUSED);
          }

          if (error instanceof AuthenticationError) {
            throw error;
          }

          throw new AuthenticationError(AuthErrorCodes.SERVICE_UNAVAILABLE);
        }
      },
    }),
  ],
  [AuthenticationType.NOAUTH]: [
    Credentials({
      name: "NoAuth",
      credentials: {},
      async authorize(): Promise<User> {
        return {
          id: "keep-user-for-no-auth-purposes",
          name: "Keep",
          email: NoAuthUserEmail,
          accessToken: "keep-token-for-no-auth-purposes",
          tenantId: NoAuthTenant,
          role: "user",
        };
      },
    }),
  ],
  [AuthenticationType.KEYCLOAK]: [
    Keycloak({
      clientId: process.env.KEYCLOAK_ID!,
      clientSecret: process.env.KEYCLOAK_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER,
      authorization: { params: { scope: "openid email profile roles" } },
    }),
  ],
  [AuthenticationType.AZUREAD]: [
    MicrosoftEntraID({
      clientId: process.env.KEEP_AZUREAD_CLIENT_ID!,
      clientSecret: process.env.KEEP_AZUREAD_CLIENT_SECRET!,
      issuer: process.env.KEEP_AZUREAD_TENANT_ID!,
      authorization: {
        params: {
          scope: `api://${process.env
            .KEEP_AZUREAD_CLIENT_ID!}/default openid profile email`,
        },
      },
    }),
  ],
};

// Create the config
const config = {
  providers:
    providerConfigs[authType as keyof typeof providerConfigs] ||
    providerConfigs[AuthenticationType.NOAUTH],
  pages: {
    signIn: "/signin",
  },
  session: {
    strategy: "jwt" as const,
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnDashboard = nextUrl.pathname.startsWith("/dashboard");
      if (isOnDashboard) {
        if (isLoggedIn) return true;
        return false;
      }
      return true;
    },
    jwt: async ({ token, user, account }) => {
      if (account && user) {
        token.accessToken =
          user.accessToken || account.access_token || account.id_token;
        token.tenantId = user.tenantId;
        token.role = user.role;

        if (authType === AuthenticationType.KEYCLOAK) {
          token.refreshToken = account.refresh_token;
          token.accessTokenExpires =
            Date.now() + (account.expires_in as number) * 1000;
        }
      } else if (
        authType === AuthenticationType.KEYCLOAK &&
        token.accessTokenExpires &&
        typeof token.accessTokenExpires === "number" &&
        Date.now() < token.accessTokenExpires
      ) {
        token = await refreshAccessToken(token);
      }

      return token;
    },
    session: async ({ session, token, user }) => {
      return {
        ...session,
        accessToken: token.accessToken as string,
        tenantId: token.tenantId as string,
        userRole: token.role as string,
        user: {
          ...session.user,
          tenantId: token.tenantId as string,
          role: token.role as string,
        },
      };
    },
  },
} satisfies NextAuthConfig;

console.log("Starting Keep frontend with auth type:", authType);

export const { handlers, auth, signIn, signOut } = NextAuth(config);
