import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";
import { customFetch } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Keycloak from "next-auth/providers/keycloak";
import Auth0 from "next-auth/providers/auth0";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { AuthError } from "next-auth";
import { AuthenticationError, AuthErrorCodes } from "@/errors";
import type { JWT } from "next-auth/jwt";
import { getApiURL } from "@/utils/apiUrl";
import {
  AuthType,
  MULTI_TENANT,
  SINGLE_TENANT,
  NO_AUTH,
  NoAuthUserEmail,
  NoAuthTenant,
} from "@/utils/authenticationType";
import type { User } from "next-auth";
import { ProxyAgent, fetch as undici } from "undici";
// https://github.com/nextauthjs/next-auth/issues/11028
export class BackendRefusedError extends AuthError {
  static type = "BackendRefusedError";
}

// Determine auth type with backward compatibility
const authTypeEnv = process.env.AUTH_TYPE;
const authType =
  authTypeEnv === MULTI_TENANT
    ? AuthType.AUTH0
    : authTypeEnv === SINGLE_TENANT
    ? AuthType.DB
    : authTypeEnv === NO_AUTH
    ? AuthType.NOAUTH
    : (authTypeEnv as AuthType);

// Determine proxy settings
const proxyUrl =
  process.env.HTTP_PROXY ||
  process.env.HTTPS_PROXY ||
  process.env.http_proxy ||
  process.env.https_proxy;

// used only if proxyUrl is set
// currently tested only on Azure AD
function proxyFetch(
  ...args: Parameters<typeof fetch>
): ReturnType<typeof fetch> {
  console.log(
    "Proxy called for URL:",
    args[0] instanceof Request ? args[0].url : args[0]
  );
  const dispatcher = new ProxyAgent(proxyUrl!);

  if (args[0] instanceof Request) {
    const request = args[0];
    // @ts-expect-error `undici` has a `duplex` option
    return undici(request.url, {
      ...args[1],
      method: request.method,
      headers: request.headers as HeadersInit,
      body: request.body,
      dispatcher,
    });
  }

  // @ts-expect-error `undici` has a `duplex` option
  return undici(args[0], { ...(args[1] || {}), dispatcher });
}

/**
 * Creates a Microsoft Entra ID provider configuration and overrides the customFetch.
 *
 * SHAHAR: this is a workaround to override the customFetch symbol in the provider
 * because in Microsoft entra it already has a customFetch symbol and we need to override it.s
 */
export const createAzureADProvider = () => {
  // Step 1: Create the base provider
  const baseConfig = {
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
  };

  const provider = MicrosoftEntraID(baseConfig);
  // if not proxyUrl, return the provider
  if (!proxyUrl) return provider;

  // Step 2: Override the `customFetch` symbol in the provider
  provider[customFetch] = async (...args: Parameters<typeof fetch>) => {
    const url = new URL(args[0] instanceof Request ? args[0].url : args[0]);
    console.log("Custom Fetch Intercepted:", url.toString());

    // Handle `.well-known/openid-configuration` logic
    if (url.pathname.endsWith(".well-known/openid-configuration")) {
      console.log("Intercepting .well-known/openid-configuration");
      const response = await proxyFetch(...args);
      const json = await response.clone().json();
      const tenantRe = /microsoftonline\.com\/(\w+)\/v2\.0/;
      const tenantId = baseConfig.issuer?.match(tenantRe)?.[1] ?? "common";
      const issuer = json.issuer.replace("{tenantid}", tenantId);
      console.log("Modified issuer:", issuer);
      return Response.json({ ...json, issuer });
    }

    // Fallback for all other requests
    return proxyFetch(...args);
  };

  // Step 3: override profile since it use fetch without customFetch
  provider.profile = async (profile, tokens) => {
    const profilePhotoSize = 48; // Default or custom size
    console.log("Fetching profile photo via proxy");

    const response = await proxyFetch(
      `https://graph.microsoft.com/v1.0/me/photos/${profilePhotoSize}x${profilePhotoSize}/$value`,
      { headers: { Authorization: `Bearer ${tokens.access_token}` } }
    );

    let image: string | null = null;
    if (response.ok && typeof Buffer !== "undefined") {
      try {
        const pictureBuffer = await response.arrayBuffer();
        const pictureBase64 = Buffer.from(pictureBuffer).toString("base64");
        image = `data:image/jpeg;base64,${pictureBase64}`;
      } catch (error) {
        console.error("Error processing profile photo:", error);
      }
    }

    // Ensure the returned object matches the User interface
    return {
      id: profile.sub,
      name: profile.name,
      email: profile.email,
      image: image ?? null,
      accessToken: tokens.access_token ?? "", // Provide empty string as fallback
    };
  };

  return provider;
};

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
  [AuthType.AZUREAD]: [createAzureADProvider()],
};

// Create the config
const config = {
  trustHost: true,
  providers:
    providerConfigs[authType as keyof typeof providerConfigs] ||
    providerConfigs[AuthType.NOAUTH],
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
        // Ensure we always have an accessToken
        // https://github.com/nextauthjs/next-auth/discussions/4255
        if (authType === AuthType.AZUREAD) {
          // Properly handle Azure AD tokens
          accessToken = account.access_token;
          // You might want to extract additional claims from the id_token if needed
          if (account.id_token) {
            try {
              // Basic JWT decode (you might want to use a proper JWT library here)
              const payload = JSON.parse(
                Buffer.from(account.id_token.split(".")[1], "base64").toString()
              );
              // Extract any additional claims you need
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

console.log("Starting Keep frontend with auth type:", authType);

export const { handlers, auth, signIn, signOut } = NextAuth(config);
