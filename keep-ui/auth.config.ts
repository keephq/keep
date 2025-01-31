import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Keycloak from "next-auth/providers/keycloak";
import Auth0 from "next-auth/providers/auth0";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { AuthError } from "next-auth";
import { AuthenticationError, AuthErrorCodes } from "@/errors";
import type { JWT } from "next-auth/jwt";
import type { User } from "next-auth";
import { getApiURL } from "@/utils/apiUrl";
import {
  AuthType,
  MULTI_TENANT,
  SINGLE_TENANT,
  NO_AUTH,
  NoAuthUserEmail,
  NoAuthTenant,
} from "@/utils/authenticationType";

export class BackendRefusedError extends AuthError {
  static type = "BackendRefusedError";
}

// Determine auth type with backward compatibility
const authTypeEnv = process.env.AUTH_TYPE;
export const authType =
  authTypeEnv === MULTI_TENANT
    ? AuthType.AUTH0
    : authTypeEnv === SINGLE_TENANT
    ? AuthType.DB
    : authTypeEnv === NO_AUTH
    ? AuthType.NOAUTH
    : (authTypeEnv as AuthType);

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

// Base provider configurations without AzureAD
const baseProviderConfigs = {
  [AuthType.AUTH0]: [
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
  [AuthType.DB]: [
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
  [AuthType.NOAUTH]: [
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
  [AuthType.KEYCLOAK]: [
    Keycloak({
      clientId: process.env.KEYCLOAK_ID!,
      clientSecret: process.env.KEYCLOAK_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER,
      authorization: { params: { scope: "openid email profile roles" } },
    }),
  ],
  [AuthType.AZUREAD]: [
    MicrosoftEntraID({
      clientId: process.env.KEEP_AZUREAD_CLIENT_ID!,
      clientSecret: process.env.KEEP_AZUREAD_CLIENT_SECRET!,
      issuer: `https://login.microsoftonline.com/${process.env
        .KEEP_AZUREAD_TENANT_ID!}/v2.0`,
      authorization: {
        params: {
          scope: `api://${process.env
            .KEEP_AZUREAD_CLIENT_ID!}/default openid profile email`,
        },
      },
      client: {
        token_endpoint_auth_method: "client_secret_post",
      },
    }),
  ],
};

export const config = {
  debug: process.env.NODE_ENV === "development",
  trustHost: true,
  providers:
    baseProviderConfigs[authType as keyof typeof baseProviderConfigs] ||
    baseProviderConfigs[AuthType.NOAUTH],
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
    jwt: async ({ token, user, account, profile }): Promise<JWT> => {
      if (account && user) {
        let accessToken: string | undefined;
        let tenantId: string | undefined = user.tenantId;
        let role: string | undefined = user.role;

        if (authType === AuthType.AZUREAD) {
          accessToken = account.access_token;
          if (account.id_token) {
            try {
              const payload = JSON.parse(
                Buffer.from(account.id_token.split(".")[1], "base64").toString()
              );
              role = payload.roles?.[0] || "user";
              tenantId = payload.tid || undefined;
            } catch (e) {
              console.warn("Failed to decode id_token:", e);
            }
          }
        } else if (authType == AuthType.AUTH0) {
          accessToken = account.id_token;
          if ((profile as any)?.keep_tenant_id) {
            tenantId = (profile as any).keep_tenant_id;
          }
          if ((profile as any)?.keep_role) {
            role = (profile as any).keep_role;
          }
        } else if (authType === AuthType.KEYCLOAK) {
          // TODO: remove this once we have a proper way to get the tenant id
          tenantId = (profile as any).keep_tenant_id || "keep";
          role = (profile as any).keep_role;
          accessToken = account.access_token;
        } else {
          accessToken =
            user.accessToken || account.access_token || account.id_token;
        }
        if (!accessToken) {
          throw new Error("No access token available");
        }

        token.accessToken = accessToken;
        token.tenantId = tenantId;
        token.role = role;

        if (authType === AuthType.KEYCLOAK) {
          token.refreshToken = account.refresh_token;
          token.accessTokenExpires =
            Date.now() + (account.expires_in as number) * 1000;
        }
      } else if (
        authType === AuthType.KEYCLOAK &&
        token.accessTokenExpires &&
        typeof token.accessTokenExpires === "number" &&
        Date.now() < token.accessTokenExpires
      ) {
        token = await refreshAccessToken(token);
        if (!token.accessToken) {
          throw new Error("Failed to refresh access token");
        }
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
          accessToken: token.accessToken as string,
          tenantId: token.tenantId as string,
          role: token.role as string,
        },
      };
    },
  },
} satisfies NextAuthConfig;
