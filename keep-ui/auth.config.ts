import type {NextAuthConfig, User} from "next-auth";
import {AuthError} from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Keycloak from "next-auth/providers/keycloak";
import Auth0 from "next-auth/providers/auth0";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import Okta from "next-auth/providers/okta";
import OneLogin from "next-auth/providers/onelogin";
import {AuthenticationError, AuthErrorCodes} from "@/errors";
import type {JWT} from "next-auth/jwt";
import {getApiURL} from "@/utils/apiUrl";
import {
  AuthType,
  MULTI_TENANT,
  NO_AUTH,
  NoAuthTenant,
  NoAuthUserEmail,
  SINGLE_TENANT,
} from "@/utils/authenticationType";

export class BackendRefusedError extends AuthError {
  static type = "BackendRefusedError";
}

const authSessionTimeout = process.env.AUTH_SESSION_TIMEOUT
  ? Number.parseInt(process.env.AUTH_SESSION_TIMEOUT)
  : 30 * 24 * 60 * 60; // Default to 30 days if not set
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

export const proxyUrl =
  process.env.HTTP_PROXY ||
  process.env.HTTPS_PROXY ||
  process.env.http_proxy ||
  process.env.https_proxy;

async function refreshAccessToken(token: any) {
  let issuerUrl = "";
  let clientId = "";
  let clientSecret = "";
  let refreshTokenUrl = "";

  switch (authType) {
    case AuthType.KEYCLOAK: {
      issuerUrl = process.env.KEYCLOAK_ISSUER || "";
      clientId = process.env.KEYCLOAK_ID || "";
      clientSecret = process.env.KEYCLOAK_SECRET || "";
      refreshTokenUrl = `${issuerUrl}/protocol/openid-connect/token`;
      break;
    }
    case AuthType.OKTA: {
      issuerUrl = process.env.OKTA_ISSUER || "";
      clientId = process.env.OKTA_CLIENT_ID || "";
      clientSecret = process.env.OKTA_CLIENT_SECRET || "";
      refreshTokenUrl = `${issuerUrl}/v1/token`;
      break;
    }
    case AuthType.ONELOGIN: {
      issuerUrl = process.env.ONELOGIN_ISSUER || "";
      clientId = process.env.ONELOGIN_CLIENT_ID || "";
      clientSecret = process.env.ONELOGIN_CLIENT_SECRET || "";
      refreshTokenUrl = `${issuerUrl}/token`;
      break;
    }
    default: {
      throw new Error("Refresh token not supported for this auth type");
    }
  }

  try {
    const response = await fetch(refreshTokenUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
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
      accessTokenExpires: Date.now() + (refreshedTokens.expires_in || 3600) * 1000,
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
      async authorize(credentials): Promise<User> {
        // Extract tenantId from callbackUrl if present
        let tenantId = NoAuthTenant;
        let name = "Keep";

        if (
          credentials &&
          typeof credentials === "object" &&
          "callbackUrl" in credentials
        ) {
          const callbackUrl = credentials.callbackUrl as string;
          const url = new URL(callbackUrl, "http://localhost");
          const urlTenantId = url.searchParams.get("tenantId");

          if (urlTenantId) {
            tenantId = urlTenantId;
            name += ` (${tenantId})`;
            console.log("Using tenantId from callbackUrl:", tenantId);
          }
        }

        return {
          id: "keep-user-for-no-auth-purposes",
          name: name,
          email: NoAuthUserEmail,
          accessToken: JSON.stringify({
            tenant_id: tenantId,
            user_id: "keep-user-for-no-auth-purposes",
          }),
          tenantIds: [
            {
              tenant_id: "keep",
              tenant_name: "Tenant of Keep (tenant_id: keep)",
            },
            {
              tenant_id: "keep2",
              tenant_name: "Tenant of another Keep (tenant_id: keep2)",
            },
          ],
          tenantId: tenantId,
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
      authorization: {
        params: {
          scope: "openid email profile",
        },
      },
      checks: ["pkce"],
    }),
  ],
  [AuthType.OKTA]: [
    Okta({
      clientId: process.env.OKTA_CLIENT_ID!,
      clientSecret: process.env.OKTA_CLIENT_SECRET!,
      issuer: process.env.OKTA_ISSUER!,
      authorization: { params: { scope: "openid email profile" } },
    }),
  ],
  [AuthType.ONELOGIN]: [
    OneLogin({
      clientId: process.env.ONELOGIN_CLIENT_ID!,
      clientSecret: process.env.ONELOGIN_CLIENT_SECRET!,
      issuer: process.env.ONELOGIN_ISSUER!,
      authorization: { params: { scope: "openid email profile groups" } },
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

let isDebug =
  process.env.AUTH_DEBUG == "true" || process.env.NODE_ENV === "development";
if (isDebug) {
  console.log("Auth debug mode enabled");
}

export const config = {
  debug: isDebug,
  trustHost: true,
  providers:
    baseProviderConfigs[authType as keyof typeof baseProviderConfigs] ||
    baseProviderConfigs[AuthType.NOAUTH],
  pages: {
    signIn: "/signin",
    error: "/error",
  },
  session: {
    strategy: "jwt" as const,
    maxAge: authSessionTimeout, // 30 days
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnDashboard = nextUrl.pathname.startsWith("/dashboard");
      if (isOnDashboard) {
        return isLoggedIn;
      }
      return true;
    },
    jwt: async ({ token, user, account, profile }): Promise<JWT> => {
      if (account && user) {
        let accessToken: string | undefined;
        let tenantId: string | undefined = user.tenantId;
        let role: string | undefined = user.role;

        // if the account is from tenant-switch provider, return the token
        if (account.provider === "tenant-switch") {
          token.accessToken = user.accessToken;
          token.tenantId = user.tenantId;
          token.role = user.role;
          return token;
        }

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
          // more than one tenants
          if ((profile as any)?.keep_tenant_ids) {
            user.tenantIds = (profile as any).keep_tenant_ids;
          }
        } else if (authType === AuthType.KEYCLOAK) {
          // TODO: remove this once we have a proper way to get the tenant id
          tenantId = (profile as any).keep_tenant_id || "keep";
          role = (profile as any).keep_role;
          accessToken = account.access_token;
        } else if (authType === AuthType.OKTA) {
          // Extract tenant and role from Okta token
          tenantId = (profile as any).keep_tenant_id || "keep";
          role = (profile as any).keep_role || "user";
          accessToken = account.access_token;
        } else if (authType === AuthType.ONELOGIN) {
          // Extract tenant and role from OneLogin token - use ID token for user data
          tenantId = (profile as any).keep_tenant_id || "keep";
          role = (profile as any).keep_role || "user";
          accessToken = account.id_token; // Use ID token instead of access token
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
          accessToken = account.access_token;

          // If user object has tenantIds from profile parsing, include them
          if (user.tenantIds) {
            token.tenantIds = user.tenantIds;
          }

          // Set default tenant and role
          token.tenantId = user.tenantId || "keep";
          token.role = user.role || "user";

          // New code: Check if multi-org mode is enabled
          if (process.env.KEYCLOAK_ROLES_FROM_GROUPS === "true") {
            try {
              // Fetch organizations from backend API
              const response = await fetch(`${getApiURL()}/auth/user/orgs`, {
                method: "GET",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${accessToken}`,
                },
              });

              if (response.ok) {
                const orgDict = await response.json();

                // Create a properly typed array (not undefined)
                const tenantArr: {
                  tenant_id: string;
                  tenant_name: string;
                  tenant_logo_url?: string;
                }[] = [];

                // Populate the array with tenant data, handling null/undefined values
                Object.entries(orgDict).forEach(([org_name, orgData]) => {
                  const tenantObject: {
                    tenant_id: string;
                    tenant_name: string;
                    tenant_logo_url?: string;
                  } = {
                    tenant_id: String((orgData as any).tenant_id),
                    tenant_name: `${org_name}`,
                  };

                  // Only add tenant_logo_url if it exists and is not null
                  const logoUrl = (orgData as any).tenant_logo_url;
                  if (logoUrl !== null && logoUrl !== undefined) {
                    tenantObject.tenant_logo_url = logoUrl;
                  }

                  tenantArr.push(tenantObject);
                });

                // Only assign if we have entries (avoids undefined)
                if (tenantArr.length > 0) {
                  token.tenantIds = tenantArr;

                  // Set default tenant to the first one if available
                  token.tenantId = tenantArr[0].tenant_id || token.tenantId;

                  console.log("Successfully processed user orgs:", tenantArr);
                } else {
                  console.warn("No orgs returned from /auth/user/orgs");
                }
              } else {
                console.error(
                  "Failed to fetch user orgs:",
                  response.statusText
                );
              }
            } catch (error) {
              console.error("Error fetching user orgs:", error);
            }
          }
        }

        // Refresh token logic for Keycloak, Okta and OneLogin
        if (authType === AuthType.KEYCLOAK || authType === AuthType.OKTA || authType === AuthType.ONELOGIN) {
          token.refreshToken = account.refresh_token;
          token.accessTokenExpires =
            Date.now() + (account.expires_in as number) * 1000;
        }
      } else if (
        (authType === AuthType.KEYCLOAK || authType === AuthType.OKTA || authType === AuthType.ONELOGIN) &&
        token.refreshToken &&
        token.accessTokenExpires &&
        typeof token.accessTokenExpires === "number" &&
        Date.now() > token.accessTokenExpires
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
          tenantIds: token.tenantIds || [],
        },
      };
    },
  },
} satisfies NextAuthConfig;

if (isDebug && authType === AuthType.AZUREAD && proxyUrl) {
  // add cookies override for AzureAD
  (config as any).cookies = {
    pkceCodeVerifier: {
      name: "authjs.pkce.code_verifier",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: false,
      },
    },
  };
}

// if debug is enabled, log the config
if (isDebug) {
  console.log("Auth config:", config);
}
