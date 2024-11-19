import NextAuth, { type AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import KeycloakProvider, {
  KeycloakProfile,
} from "next-auth/providers/keycloak";
import Auth0Provider from "next-auth/providers/auth0";
import AzureADProvider from "next-auth/providers/azure-ad";
import { HttpsProxyAgent } from "https-proxy-agent";

import { getApiURL } from "utils/apiUrl";
import {
  AuthenticationType,
  NoAuthUserEmail,
  NoAuthTenant,
  MULTI_TENANT,
  SINGLE_TENANT,
  NO_AUTH,
} from "utils/authenticationType";
import { OAuthConfig } from "next-auth/providers";

const authTypeEnv = process.env.AUTH_TYPE;
let authType;

// Backward compatibility
if (authTypeEnv === MULTI_TENANT) {
  authType = AuthenticationType.AUTH0;
} else if (authTypeEnv === SINGLE_TENANT) {
  authType = AuthenticationType.DB;
} else if (authTypeEnv === NO_AUTH) {
  authType = AuthenticationType.NOAUTH;
} else {
  authType = authTypeEnv;
}
/*

This file implements different authentication flows:
1. Multi-tenant authentication using Auth0
2. Single-tenant authentication using username/password
3. No authentication
4. Keycloak authentication
5. Azure AD authentication

Depends on authType which can be NO_AUTH, SINGLE_TENANT, MULTI_TENANT, KEYCLOAK, or AZURE_AD
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
      if ((profile as any)?.keep_role) {
        token.keep_role = (profile as any).keep_role;
      }

      // on github, prefer given name over nickname (default?)
      if ((profile as any)?.given_name) {
        const givenName = (profile as any).given_name;
        token.name = givenName;
      } else if ((profile as any)?.name) {
        // split by " " and take the first part
        const name = (profile as any).name as string;
        const nameParts = name.split(" ");
        // verify that the name is not empty (should not happen, but just in case)
        if (nameParts.length > 0) {
          token.name = nameParts[0];
        }
      }

      return token;
    },
    async session({ session, token }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      session.tenantId = token.keep_tenant_id as string;
      session.userRole = token.keep_role as string;
      return session;
    },
  },
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
          const role = user.role as string;
          // Assuming the response contains the user's data if authentication was successful
          if (user && user.accessToken) {
            return {
              ...user,
              accessToken,
              tenantId,
              role,
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
        token.email = user.email;
        token.role = user.role;
      }
      return token;
    },
    async session({ session, token, user }) {
      // https://next-auth.js.org/configuration/callbacks#session-callback
      session.accessToken = token.accessToken as string;
      session.tenantId = token.tenantId as string;
      session.userRole = token.role as string;
      return session;
    },
  },
} as AuthOptions;

async function refreshAccessToken(token: any) {
  const issuerUrl = process.env.KEYCLOAK_ISSUER;
  const refreshTokenUrl = `${issuerUrl}/protocol/openid-connect/token`;

  const params = new URLSearchParams({
    client_id: process.env.KEYCLOAK_ID!, // Using non-null assertion (!) because it is required
    client_secret: process.env.KEYCLOAK_SECRET!, // Using non-null assertion (!)
    grant_type: "refresh_token",
    refresh_token: token.refreshToken, // Assuming refreshToken is correctly stored and is a string
  });

  const response = await fetch(refreshTokenUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params, // Directly using URLSearchParams instance
  });

  const refreshedTokens = await response.json();

  if (!response.ok) {
    console.error("Failed to refresh token:", refreshedTokens);
    throw new Error(
      `Refresh token failed: ${response.status} ${response.statusText}`
    );
  }

  return {
    ...token,
    accessToken: refreshedTokens.access_token,
    accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000,
    refreshToken: refreshedTokens.refresh_token ?? token.refreshToken, // Using the new refresh token if available
  };
}

// No authentication
const noAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "NoAuth",
      credentials: {},
      async authorize(credentials, req) {
        // Return a static user object with a predefined token
        return {
          id: "keep-user-for-no-auth-purposes",
          name: "Keep",
          email: NoAuthUserEmail,
          tenantId: NoAuthTenant,
          accessToken: "keep-token-for-no-auth-purposes", // Static token for no-auth purposes - DO NOT USE IN PRODUCTION
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // If the user object exists, set the static token
      if (user) {
        token.accessToken = user.accessToken;
        token.tenantId = user.tenantId;
        token.email = user.email;
        token.role = user.role;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.tenantId = token.tenantId as string;
      session.userRole = token.role as string;
      return session;
    },
  },
  pages: {
    signIn: "/signin",
  },
} as AuthOptions;

const keycloakAuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_ID!,
      clientSecret: process.env.KEYCLOAK_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER,
      authorization: {
        params: { scope: "openid email profile roles" },
      },
    }),
  ],
  pages: {
    signIn: "/signin",
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, account, profile, user }) {
      // account is populated on login
      if (account) {
        token.accessToken = account.access_token;
        token.id_token = account.id_token;
        token.refreshToken = account.refresh_token;
        token.accessTokenExpires =
          Date.now() + (account.refresh_expires_in as number) * 1000;
        // token.tenantId = profile?.active_organization.id;
        token.keep_tenant_id = "keep";
      } else if (Date.now() < (token.accessTokenExpires as number)) {
        // Return previous token if it has not expired yet
        return token;
      }
      // Access token has expired, try to update it
      console.log("Refreshing access token");
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.tenantId = token.keep_tenant_id as string;
      return session;
    },
  },
  events: {
    async signOut({ token }: { token: any }) {
      console.log("Signing out from Keycloak");
      const issuerUrl = (
        authOptions.providers.find(
          (p) => p.id === "keycloak"
        ) as OAuthConfig<KeycloakProfile>
      ).options!.issuer!;
      const logOutUrl = new URL(`${issuerUrl}/protocol/openid-connect/logout`);
      logOutUrl.searchParams.set("id_token_hint", token.id_token);
      try {
        // Perform the logout request.
        const response = await fetch(logOutUrl.toString(), {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error(
            `Logout failed: ${response.status} ${response.statusText}`
          );
        }
      } catch (error) {
        console.error("Error signing out from Keycloak:", error);
      }
      console.log("Logged out from Keycloak"); // :)
    },
  },
} as AuthOptions;

const azureADAuthOptions = {
  providers: [
    AzureADProvider({
      clientId: process.env.KEEP_AZUREAD_CLIENT_ID!,
      clientSecret: process.env.KEEP_AZUREAD_CLIENT_SECRET!,
      tenantId: process.env.KEEP_AZUREAD_TENANT_ID!,
      authorization: {
        params: {
          scope:
            "api://" +
            process.env.KEEP_AZUREAD_CLIENT_ID! +
            "/default openid profile email",
        },
      },
      checks: ["pkce"],
      client: {
        token_endpoint_auth_method: "client_secret_post",
      },
      /*
      httpOptions: process.env.http_proxy ? {
        agent: new HttpsProxyAgent(process.env.http_proxy),
      } : undefined,
      */
    }),
  ],
  pages: {
    signIn: "/signin",
  },
  debug: true,
  cookies: {
    pkceCodeVerifier: {
      name: "next-auth.pkce.code_verifier",
      options: {
        httpOnly: true,
        sameSite: "none",
        path: "/",
        secure: true,
        maxAge: 900, // 15 minutes
      },
    },
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async redirect({ url, baseUrl }) {
      console.log("Redirecting to: ", url);
      return baseUrl;
    },
    async jwt({ token, account, profile }) {
      if (account) {
        console.log("Account: ", account);
        console.log("access_token: ", account.access_token);
        token.accessToken = account.access_token;
        token.keep_tenant_id = process.env.KEEP_AZUREAD_TENANT_ID;
        token.keep_role = "user"; // Default role - adjust as needed
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.tenantId = token.keep_tenant_id as string;
      session.userRole = token.keep_role as string;
      return session;
    },
  },
} as AuthOptions;

console.log("Starting Keep frontend with auth type: ", authType);
export const authOptions =
  authType === AuthenticationType.AUTH0
    ? multiTenantAuthOptions
    : authType === AuthenticationType.DB
    ? singleTenantAuthOptions
    : authType === AuthenticationType.KEYCLOAK
    ? keycloakAuthOptions
    : authType === AuthenticationType.AZUREAD
    ? azureADAuthOptions
    : // oauth2proxy same configuration as noauth
      noAuthOptions;

export default NextAuth(authOptions);
